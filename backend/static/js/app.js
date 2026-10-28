(function(){var d=document,$=function(s,r){return(r||d).querySelector(s)};
var tg=$('#themeToggle');if(tg){var paint=function(){var m=d.documentElement.dataset.theme;tg.textContent=m==='dark'?'☀':'☾';tg.setAttribute('aria-label',m==='dark'?'Switch to light mode':'Switch to dark mode')};paint();
tg.addEventListener('click',function(){var m=d.documentElement.dataset.theme==='dark'?'light':'dark';d.documentElement.dataset.theme=m;try{localStorage.setItem('theme',m)}catch(e){}paint()})}
d.addEventListener('submit',function(e){var f=e.target;if(f.dataset.confirm&&!confirm(f.dataset.confirm)){e.preventDefault();return}
if(f.dataset.nobusy!==undefined||f.method==='get')return;if(f.dataset.busy){e.preventDefault();return}f.dataset.busy='1';
var b=e.submitter||$('button:not([type=button])',f);if(b){setTimeout(function(){b.dataset.label=b.textContent;b.disabled=true;b.textContent='Please wait…'},0)}});
addEventListener('pageshow',function(){d.querySelectorAll('form[data-busy]').forEach(function(f){delete f.dataset.busy;f.querySelectorAll('button[disabled]').forEach(function(b){b.disabled=false;if(b.dataset.label)b.textContent=b.dataset.label})})});
if(window.L)d.querySelectorAll('[data-map]').forEach(function(el){var lat=parseFloat(el.dataset.lat),lng=parseFloat(el.dataset.lng),pick=el.hasAttribute('data-pick'),la=$('#latitude'),lo=$('#longitude'),has=!pick||(la&&la.value);
if(pick&&has){lat=parseFloat(la.value);lng=parseFloat(lo.value)}
var m=L.map(el).setView([lat,lng],15);L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(m);
var mk=null,put=function(ll){if(mk)mk.setLatLng(ll);else mk=L.circleMarker(ll,{radius:10,color:'#1E3A5F',fillColor:'#F4A825',fillOpacity:1}).addTo(m)};if(has)put([lat,lng]);
if(pick)m.on('click',function(e){put(e.latlng);la.value=e.latlng.lat.toFixed(6);lo.value=e.latlng.lng.toFixed(6);$('#pinText').textContent='Pinned: '+la.value+', '+lo.value})})})();
