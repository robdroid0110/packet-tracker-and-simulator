/* Size the dock around wrapped controls without changing stored user sizes. */
(() => {
 const strip=document.getElementById('timeStrip');
 let previous=0;
 const observer=new ResizeObserver(() => {
  const height=Math.ceil(strip.getBoundingClientRect().height);
  if(height===previous)return;
  previous=height;
  document.documentElement.style.setProperty('--dock-time-height',height+'px');
 });
 observer.observe(strip);
})();
