function hasDImg(k){return DATA.design_images&&DATA.design_images[k];}
function getDesignPreview(){
  var pv=document.getElementById('designPreview');
  if(!pv){
    pv=document.createElement('div');
    pv.id='designPreview';
    document.body.appendChild(pv);
  }
  return pv;
}
function moveDesignPreview(e){
  var pv=getDesignPreview();
  if(pv.style.display==='none')return;
  var x=e.clientX+18,y=e.clientY+18;
  var w=pv.offsetWidth||280,h=pv.offsetHeight||340;
  if(x+w>window.innerWidth-8)x=e.clientX-w-18;
  if(y+h>window.innerHeight-8)y=e.clientY-h-18;
  pv.style.left=Math.max(8,x)+'px';
  pv.style.top=Math.max(8,y)+'px';
}
function showDesignPreview(k,e){
  if(!hasDImg(k))return hideDesignPreview();
  var pv=getDesignPreview();
  var src=DATA.design_images[k];
  pv.innerHTML='<img src="'+src+'" alt="'+k.replace(/"/g,'&quot;')+'"><div class="dp-title">'+k+'</div>';
  pv.style.display='block';
  if(e)moveDesignPreview(e);
}
function hideDesignPreview(){
  var pv=document.getElementById('designPreview');
  if(pv)pv.style.display='none';
}
function dLbl(k,text){
  if(!hasDImg(k))return text||k;
  var safe=(text||k).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/"/g,'&quot;');
  return'<span class="dhp" data-dimg="'+k.replace(/"/g,'&quot;')+'">'+safe+'</span>';
}
function bindChartDesignPreview(chart){
  if(!chart||!DATA.design_images||!Object.keys(DATA.design_images).length)return;
  var canvas=chart.canvas;
  if(canvas._dhpBound)return;
  canvas._dhpBound=true;
  function chartPoint(e){
    var rect=canvas.getBoundingClientRect();
    return{x:e.clientX-rect.left,y:e.clientY-rect.top};
  }
  function legendIndex(e){
    var legend=chart.legend;
    if(!legend||!legend.legendHitBoxes)return-1;
    var pt=chartPoint(e);
    for(var i=0;i<legend.legendHitBoxes.length;i++){
      var b=legend.legendHitBoxes[i];
      if(pt.x>=b.left&&pt.x<=b.left+b.width&&pt.y>=b.top&&pt.y<=b.top+b.height)return i;
    }
    return-1;
  }
  function handleMove(e){
    var li=legendIndex(e);
    if(li>=0){
      var lk=chart.data.labels[li];
      if(hasDImg(lk)){showDesignPreview(lk,e);return;}
    }
    var pts=chart.getElementsAtEventForMode(chartPoint(e),'nearest',{intersect:true},true);
    if(pts.length){
      var k=chart.data.labels[pts[0].index];
      if(hasDImg(k)){showDesignPreview(k,e);return;}
    }
    hideDesignPreview();
  }
  canvas.addEventListener('mousemove',handleMove);
  canvas.addEventListener('mouseleave',hideDesignPreview);
}
function initDesignPreview(){
  if(!DATA.design_images||!Object.keys(DATA.design_images).length)return;
  getDesignPreview();
  var active=null;
  document.addEventListener('mouseover',function(e){
    var el=e.target.closest('.dhp');
    if(!el){
      if(active&&!active.contains(e.target))hideDesignPreview();
      return;
    }
    active=el;
    var k=el.getAttribute('data-dimg');
    showDesignPreview(k,e);
  });
  document.addEventListener('mousemove',function(e){
    moveDesignPreview(e);
  });
  document.addEventListener('mouseout',function(e){
    var el=e.target.closest('.dhp');
    if(el&&!el.contains(e.relatedTarget)){
      hideDesignPreview();
      active=null;
    }
  });
}
