async function getToken(){const{hfcToken}=await chrome.storage.session.get(["hfcToken"]);return hfcToken||null;}
async function setToken(tok){await chrome.storage.session.set({hfcToken:tok});}
async function openSidePanel(tabId){if(chrome.sidePanel&&tabId){try{await chrome.sidePanel.open({tabId})}catch(_){}}}

chrome.runtime.onInstalled.addListener(()=>{
  chrome.contextMenus.create({id:"hfc-jha",title:"Safety  Generate JHA from selection",contexts:["selection"]});
  chrome.contextMenus.create({id:"hfc-sds",title:"Safety  Find SDS for %s",contexts:["selection"]});
});

chrome.contextMenus.onClicked.addListener(async(info,tab)=>{
  const selection=info.selectionText||"";
  const token=await getToken();
  if(!token){ chrome.tabs.create({url:"https://<orchestrator>.onrender.com/ext/login"}); return; }

  if(info.menuItemId==="hfc-jha"){
    const res=await fetch("https://<orchestrator>.onrender.com/ext/safety/jha",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":`Bearer ${token}`},
      body:JSON.stringify({task:selection,location:"Job site",crew_size:2})});
    const data=await res.json(); await chrome.storage.session.set({lastSafetyDoc:data}); await openSidePanel(tab?.id);
  }

  if(info.menuItemId==="hfc-sds"){
    const res=await fetch("https://<orchestrator>.onrender.com/ext/safety/sds",{method:"POST",
      headers:{"Content-Type":"application/json","Authorization":`Bearer ${token}`},
      body:JSON.stringify({query:selection})});
    const data=await res.json(); await chrome.storage.session.set({lastSdsResults:data}); await openSidePanel(tab?.id);
  }
});

chrome.runtime.onMessageExternal.addListener(async(msg,sender,sendResponse)=>{
  if(msg&&msg.type==="HFC_TOKEN"&&msg.token){ await setToken(msg.token); sendResponse({ok:true}); }
});
