import {chromium} from 'playwright';
import {spawn,execFileSync} from 'node:child_process';
import {mkdtemp,readFile,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';
import {createServer} from 'node:net';

const root=resolve(import.meta.dirname,'../..');
const scratch=await mkdtemp(join(tmpdir(),'sunny-desktop-'));
const port=await new Promise(r=>{const s=createServer();s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>r(p))})});
const password='Desktop-browser-2026!';const changed=password+'changed';
const python=process.env.SUNNY_QA_PYTHON||join(root,'.venv/bin/python');
const appRoot=process.env.SUNNY_QA_APP_ROOT||root;
const server=spawn(python,['-m','backend.scripts.desktop','--no-browser','--data-dir',scratch,'--port',String(port)],{cwd:appRoot,env:{...process.env,OPENAI_API_KEY:'',PYTHONDONTWRITEBYTECODE:'1'},stdio:['ignore','pipe','pipe']});
let serverLog='';server.stderr.on('data',x=>serverLog+=x.toString());
let browser;const results=[];const errors=[];
function check(ok,label){if(!ok)throw Error(label);results.push(label)}
async function formSave(page){await page.getByRole('dialog').getByRole('button',{name:'Xác nhận',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'})}
async function customer(page,code){await page.goto('http://127.0.0.1:'+port+'/erp/customers');await page.getByRole('button',{name:'Tạo mới',exact:true}).click();const d=page.getByRole('dialog');await d.getByLabel(/^Mã khách hàng/).fill(code);await d.getByLabel(/^Tên \*/).fill('Khách '+code);await formSave(page);await page.getByRole('cell',{name:code,exact:true}).waitFor()}
async function login(page,pass){await page.goto('http://127.0.0.1:'+port);await page.getByLabel('Tên đăng nhập').fill('owner');await page.getByLabel('Mật khẩu',{exact:true}).fill(pass);await page.getByRole('button',{name:'Đăng nhập',exact:true}).click()}
try{
  let session;
  for(let i=0;i<120;i++){try{session=JSON.parse(await readFile(join(scratch,'desktop-session.json'),'utf8'));break}catch{}if(server.exitCode!==null)throw Error(serverLog);await new Promise(r=>setTimeout(r,100))}
  if(!session)throw Error('Control startup timed out');
  browser=await chromium.launch({executablePath:process.env.SUNNY_QA_CHROME||undefined,headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1360,height:1000}});page.on('pageerror',e=>errors.push(e.message));
  await page.goto(session.url);await page.getByRole('heading',{name:'Tạo không gian làm việc của anh'}).waitFor();check(true,'Clean first launch opens setup instead of demo data');
  await page.getByLabel('Tên doanh nghiệp').fill('SUNNY Browser Acceptance');await page.getByLabel('Tên đăng nhập quản trị').fill('owner');await page.getByLabel('Mật khẩu quản trị (12–128 ký tự)').fill(password);await page.getByLabel('Nhập lại mật khẩu',{exact:true}).fill(password);await page.getByRole('button',{name:'Tạo tài khoản và mở máy chủ'}).click();await page.getByText('ĐANG CHẠY',{exact:true}).waitFor();check(true,'Browser setup provisions a real organization and starts the ERP');
  await page.screenshot({path:join(scratch,'control-desktop.png'),fullPage:true,animations:'disabled'});
  const app=await browser.newPage({viewport:{width:1360,height:950}});app.on('pageerror',e=>errors.push(e.message));await login(app,password);await app.getByRole('heading',{name:'Đổi mật khẩu để tiếp tục'}).waitFor();await app.getByLabel(/^Mật khẩu hiện tại/).fill(password);await app.getByLabel(/^Mật khẩu mới/).fill(changed);await app.getByRole('button',{name:'Lưu mật khẩu mới'}).click();await app.getByRole('heading',{name:'Đăng nhập hệ thống'}).waitFor();await login(app,changed);await app.getByRole('heading',{name:'Chào Quản trị hệ thống'}).waitFor();check(true,'First administrator must change the password before working');
  await customer(app,'BEFORE-BACKUP');check(true,'Fresh desktop installation saves business records');
  const optionBefore=await page.getByLabel('Các bản sao lưu hiện có').locator('option').allTextContents();
  await page.getByRole('button',{name:'Tạo bản sao lưu đầy đủ',exact:true}).click();await page.getByRole('status').filter({hasText:'Đã tạo bản sao lưu:'}).waitFor();const backup=(await page.getByRole('status').innerText()).split(': ').at(-1);await page.getByLabel('Các bản sao lưu hiện có').selectOption(backup);check(backup.endsWith('.sunnybackup'),'One-click full backup creates a verified archive');
  await customer(app,'AFTER-BACKUP');const oldAccess=await app.evaluate(()=>sessionStorage.getItem('sunny_access'));
  await page.getByText('Khôi phục dữ liệu từ bản sao lưu',{exact:true}).click();await page.getByLabel('Nhập KHOI PHUC để xác nhận').fill('KHOI PHUC');await page.getByRole('button',{name:'Khôi phục bản đang chọn'}).click();await page.getByRole('status').filter({hasText:'Đã khôi phục.'}).waitFor();check(true,'Restore stops the server, preserves prior data, verifies and restarts');
  const rejected=await fetch('http://127.0.0.1:'+port+'/api/v1/auth/me',{headers:{Authorization:'Bearer '+oldAccess}});check(rejected.status===401,'Restored database rejects sessions from before restore');
  await app.evaluate(()=>sessionStorage.clear());await login(app,changed);await app.getByRole('heading',{name:'Chào Quản trị hệ thống'}).waitFor();await app.goto('http://127.0.0.1:'+port+'/erp/customers');await app.getByRole('cell',{name:'BEFORE-BACKUP',exact:true}).waitFor();check(await app.getByRole('cell',{name:'AFTER-BACKUP',exact:true}).count()===0,'Restore recovers the selected data snapshot');
  await page.getByRole('button',{name:'Dừng máy chủ',exact:true}).click();await page.getByText('ĐÃ DỪNG',{exact:true}).waitFor();let down=false;try{await fetch('http://127.0.0.1:'+port+'/api/v1/health')}catch{down=true}check(down,'Stop shuts down the actual ERP process');
  await page.getByRole('button',{name:'Khởi động',exact:true}).click();await page.getByText('ĐANG CHẠY',{exact:true}).waitFor();check((await fetch('http://127.0.0.1:'+port+'/api/v1/health')).ok,'Restart opens the persisted database');
  await page.getByText('Truy cập từ điện thoại và vị trí dữ liệu',{exact:true}).click();await page.getByLabel('Cho phép ERP truy cập qua Wi-Fi nội bộ').check();await page.getByRole('button',{name:'Lưu chế độ Wi-Fi'}).click();await page.getByRole('status').filter({hasText:'Đã thực hiện thành công.'}).waitFor();check(await page.getByLabel('Cho phép ERP truy cập qua Wi-Fi nội bộ').isChecked(),'Local operator can enable the LAN server');
  await page.setViewportSize({width:390,height:844});check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Local control center fits a 390 px viewport');await page.screenshot({path:join(scratch,'control-mobile.png'),fullPage:true,animations:'disabled'});
  check(errors.length===0,'No browser runtime errors in setup or operations');
  const report={passed:results.length,checks:results,browser_errors:errors,platform:process.env.SUNNY_QA_PLATFORM||process.platform+' '+execFileSync(python,['--version'],{encoding:'utf8'}).trim()+'; real subprocess and Chromium',native_windows:false,live_openai:false};await writeFile(process.env.SUNNY_QA_RESULT||join(root,'docs/current/desktop_acceptance.json'),JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify({...report,internal_screenshots:scratch}));
  await page.getByRole('button',{name:'Đóng SUNNY ERP và dừng máy chủ'}).click();
}catch(e){console.error(e.stack);if(browser)for(const [i,p] of browser.contexts().flatMap(c=>c.pages()).entries())await p.screenshot({path:join(scratch,'failure-'+i+'.png'),fullPage:true}).catch(()=>{});console.error('Internal QA: '+scratch+'\n'+serverLog);process.exitCode=1}
finally{await browser?.close();server.kill('SIGTERM')}
