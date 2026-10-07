// Run the actual page script with a minimal DOM, without network or camera access.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync(require('node:path').join(__dirname,process.argv[2]||'../deployment/edge/local_dashboard.html'),'utf8');
const code=html.match(/<script>([\s\S]*?)<\/script>/)[1];
function element(svg=false){const e={textContent:'',className:'',disabled:false,style:{},src:'',value:'',children:[],attributes:{},append(...n){this.children.push(...n)},replaceChildren(...n){this.children=n},setAttribute(k,v){this.attributes[k]=v},toggleAttribute(k,on){if(on)this.attributes[k]='';else delete this.attributes[k]},removeAttribute(k){delete this.attributes[k]},addEventListener(){},reset(){},showModal(){},close(){}};
if(svg)Object.defineProperty(e,'hidden',{set(){throw Error('SVG visibility must use the hidden attribute')}});else e.hidden=false;return e}
const nodes=new Map(),get=id=>{if(!nodes.has(id))nodes.set(id,element(id==='chart'));return nodes.get(id)};
const location={hash:''};
const context=vm.createContext({console,URLSearchParams,URL,Date,Number,Math,Infinity,Error,AbortSignal,
 document:{hidden:false,getElementById:get,querySelector:()=>({content:'fixture-token'}),querySelectorAll:()=>[],createElement:()=>element(),createTextNode:s=>({textContent:s}),createElementNS:()=>element(),addEventListener(){}},
 location,history:{replaceState(_a,_b,hash){location.hash=hash}},window:{scrollTo(){},addEventListener(){}},setTimeout(){},clearTimeout(){},setInterval(){},fetch:()=>new Promise(()=>{})});
vm.runInContext(code,context);
const now=Date.now(),cloud=html.includes('云端检测工作台');
const sample={edge_connected:true,server_time:now/1000,runtime_age_s:.1,storage_available:true,total_records:1,pending_records:0,build:'fixture',trend:[{timestamp:new Date(now).toISOString(),fall_probability:.9}],telemetry:{},state_counts:{},runtime:{valid_pose:false,last_prediction:.9,last_prediction_at:new Date(now).toISOString(),started_at:new Date(now-60000).toISOString(),last_capture_at:new Date(now).toISOString(),backend:'hailo',predictions:1,frames:2,last_state:'confirmed'},camera_control:{enabled:true,state:'active'}};
function display(value){context.fixture=value;vm.runInContext('display(fixture)',context)}
display(sample);assert.equal(get('score').textContent,'—');assert.equal(get('state').textContent,'等待完整人体');
display({...sample,runtime:{...sample.runtime,valid_pose:true,last_prediction_at:new Date(now-3000).toISOString()}});assert.equal(get('score').textContent,'—');
display({...sample,runtime:{...sample.runtime,valid_pose:true}});assert.equal(get('score').textContent,'90.0%');assert.equal(get('state').textContent,'跌倒告警');assert.ok(get('chart').children.every(n=>!JSON.stringify(n.attributes).includes('NaN')));
display({...sample,camera_control:{enabled:true,state:'inactive'}});assert.equal(get('state').textContent,'检测已暂停');assert.equal(get('score').textContent,'—');
vm.runInContext('unavailable()',context);assert.ok('hidden' in get('chart').attributes);assert.equal(get('score').textContent,'—');assert.equal(get('connection').textContent,cloud?'云端页面未连接':'本地页面未连接');
if(cloud){display({...sample,runtime:{},runtime_age_s:null,edge_connected:false,pending_records:null});assert.equal(get('state').textContent,'树莓派暂不可达');assert.equal(get('score').textContent,'—');assert.equal(get('total').textContent,'1');assert.equal(get('pending').textContent,'—');}
console.log('UI checks passed: invalid pose, old prediction, active alert, paused camera, lost connection, finite chart coordinates.');
