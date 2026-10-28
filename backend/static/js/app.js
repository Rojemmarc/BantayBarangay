(function(){var d=document,$=function(s,r){return(r||d).querySelector(s)};
var tg=$('#themeToggle');if(tg){var paint=function(){var m=d.documentElement.dataset.theme;tg.textContent=m==='dark'?'☀':'☾';tg.setAttribute('aria-label',m==='dark'?'Switch to light mode':'Switch to dark mode')};paint();
tg.addEventListener('click',function(){var m=d.documentElement.dataset.theme==='dark'?'light':'dark';d.documentElement.dataset.theme=m;try{localStorage.setItem('theme',m)}catch(e){}paint()})}
d.addEventListener('submit',function(e){var f=e.target;if(f.dataset.confirm&&!confirm(f.dataset.confirm)){e.preventDefault();return}
if(f.dataset.nobusy!==undefined||f.method==='get')return;if(f.dataset.busy){e.preventDefault();return}f.dataset.busy='1';
var b=e.submitter||$('button:not([type=button])',f);if(b){setTimeout(function(){b.dataset.label=b.textContent;b.disabled=true;b.textContent='Please wait…'},0)}});
addEventListener('pageshow',function(){d.querySelectorAll('form[data-busy]').forEach(function(f){delete f.dataset.busy;f.querySelectorAll('button[disabled]').forEach(function(b){b.disabled=false;if(b.dataset.label)b.textContent=b.dataset.label})})});
if(window.L){d.querySelectorAll('[data-map]').forEach(function(el){var lat=parseFloat(el.dataset.lat),lng=parseFloat(el.dataset.lng),pick=el.hasAttribute('data-pick'),la=$('#latitude'),lo=$('#longitude'),status=$('#mapStatus'),has=!pick||(la&&la.value&&lo&&lo.value);
if(pick&&has){lat=parseFloat(la.value);lng=parseFloat(lo.value);has=Number.isFinite(lat)&&Number.isFinite(lng)&&lat>=-90&&lat<=90&&lng>=-180&&lng<=180;if(!has){lat=parseFloat(el.dataset.lat);lng=parseFloat(el.dataset.lng)}}
var m=L.map(el).setView([lat,lng],15),tiles=L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'© OpenStreetMap contributors',maxZoom:19}).addTo(m);
var mk=null,put=function(ll){if(mk)mk.setLatLng(ll);else mk=L.circleMarker(ll,{radius:10,color:'#1E3A5F',fillColor:'#F4A825',fillOpacity:1}).addTo(m)};
if(has)put([lat,lng]);
tiles.on('tileerror',function(){if(status)status.textContent='Map tiles could not be loaded. Enter the latitude and longitude manually below.'});
requestAnimationFrame(function(){m.invalidateSize()});addEventListener('resize',function(){m.invalidateSize()});
if(pick){var sync=function(){var a=parseFloat(la.value),o=parseFloat(lo.value);if(la.value&&lo.value&&Number.isFinite(a)&&Number.isFinite(o)&&a>=-90&&a<=90&&o>=-180&&o<=180){var ll=L.latLng(a,o);put(ll);m.setView(ll,Math.max(m.getZoom(),15));$('#pinText').textContent='Pinned: '+a.toFixed(6)+', '+o.toFixed(6)}else if(!la.value||!lo.value)$('#pinText').textContent='No pin yet'};
m.on('click',function(e){la.value=e.latlng.lat.toFixed(6);lo.value=e.latlng.lng.toFixed(6);put(e.latlng);$('#pinText').textContent='Pinned: '+la.value+', '+lo.value});la.addEventListener('input',sync);lo.addEventListener('input',sync)}
});}
else if(d.querySelector('[data-map]')){var status=$('#mapStatus');if(status)status.textContent='The map could not be initialized. Enter the latitude and longitude manually below.'}
})();
