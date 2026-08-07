function hasDImg(k){return DATA.design_images&&DATA.design_images[k];}
function dLbl(k,text){
  if(!hasDImg(k))return text||k;
  var safe=(text||k).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  return'<span class="dhp" data-dimg="'+k.replace(/"/g,'&quot;')+'">'+safe+'</span>';
}
function initDesignPreview(){
  if(!DATA.design_images||!Object.keys(DATA.design_images).length)return;
  var pv=document.getElementById('designPreview');
  if(!pv){
    pv=document.createElement('div');
    pv.id='designPreview';
    document.body.appendChild(pv);
  }
  var active=null;
  document.addEventListener('mouseover',function(e){
    var el=e.target.closest('.dhp');
    if(!el){
      if(active&&!active.contains(e.target))pv.style.display='none';
      return;
    }
    active=el;
    var k=el.getAttribute('data-dimg');
    var src=DATA.design_images[k];
    if(!src){pv.style.display='none';return;}
    pv.innerHTML='<img src="'+src+'" alt="'+k.replace(/"/g,'&quot;')+'"><div class="dp-title">'+k+'</div>';
    pv.style.display='block';
  });
  document.addEventListener('mousemove',function(e){
    if(pv.style.display==='none')return;
    var x=e.clientX+18,y=e.clientY+18;
    var w=pv.offsetWidth||280,h=pv.offsetHeight||340;
    if(x+w>window.innerWidth-8)x=e.clientX-w-18;
    if(y+h>window.innerHeight-8)y=e.clientY-h-18;
    pv.style.left=Math.max(8,x)+'px';
    pv.style.top=Math.max(8,y)+'px';
  });
  document.addEventListener('mouseout',function(e){
    var el=e.target.closest('.dhp');
    if(el&&!el.contains(e.relatedTarget)){
      pv.style.display='none';
      active=null;
    }
  });
}
