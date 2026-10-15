function rTallas(){
  var TORD={'XS':0,'S':1,'M':2,'L':3,'XL':4,'2XL':5,'3XL':6};
  var rows=fr();var generos=ag(rows,'genero').map(function(x){return x.k;});
  var grid=document.getElementById('tallasGrid');var cols=generos.length===1?'1fr':generos.length===2?'1fr 1fr':'1fr 1fr 1fr';
  grid.style.cssText='display:grid;grid-template-columns:'+cols+';gap:14px;margin-bottom:14px';
  grid.innerHTML=generos.map(function(g){return'<div class="card"><h3 style="color:'+gcol(g)+'">'+(GICO[g]||'')+' '+g+' — Tallas</h3><div class="sub">Distribución de tallas vendidas</div><div class="cw"><canvas id="cTalla_'+g+'"></canvas></div></div>';}).join('');
  generos.forEach(function(g){
    var gRows=rows.filter(function(r){return r.genero===g;});
    var byT=ag(gRows,'talla').slice().sort(function(a,b){return(TORD[a.k]||99)-(TORD[b.k]||99);});
    var col=gcol(g);
    var maxPct=Math.max.apply(null,byT.map(function(x){return x.pct;}).concat([0]));
    mc('cTalla_'+g,'bar',{labels:byT.map(function(x){return x.k;}),datasets:[{data:byT.map(function(x){return x.pct;}),backgroundColor:col+'bb',borderColor:col,borderWidth:1,borderRadius:5,_units:byT.map(function(x){return x.v;})}]},Object.assign(bo(),{plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e1f2b',borderColor:'#2a2b3a',borderWidth:1,titleFont:{family:'Syne',weight:'bold'},bodyFont:{family:'DM Sans'},padding:10,callbacks:{title:function(items){return 'Talla '+items[0].label;},label:function(ctx){return ' '+ctx.parsed.y.toFixed(1)+'%  ('+ctx.dataset._units[ctx.dataIndex]+' und)';}}},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:12},textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.7)',anchor:'end',align:'start',formatter:function(v){return v.toFixed(1)+'%';}}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11},callback:function(v){return v+'%';}},max:Math.min(100,Math.ceil(maxPct*1.3/5)*5||100)}}}));
  });
  var byColor=ag(rows,'color').slice(0,12);
  var tallas=ag(rows,'talla').map(function(x){return x.k;}).sort(function(a,b){return(TORD[a]||99)-(TORD[b]||99);});
  var m2=ag2(rows,'color','talla');var mx=0;
  byColor.forEach(function(c){tallas.forEach(function(t){var v=(m2[c.k]&&m2[c.k][t])||0;if(v>mx)mx=v;});});
  var h='<table class="hmt"><thead><tr><th></th>'+tallas.map(function(t){return'<th>'+t+'</th>';}).join('')+'</tr></thead><tbody>';
  byColor.forEach(function(x){
    h+='<tr><td class="rl"><span class="chip" style="background:'+cn(x.k)+'"></span>'+x.k+'</td>'+
      tallas.map(function(t){var v=(m2[x.k]&&m2[x.k][t])||0;return'<td style="background:'+hb(v,mx)+';color:'+ht(v,mx)+'" title="'+x.k+' T'+t+': '+v+'">'+v+'</td>';}).join('')+'</tr>';
  });
  document.getElementById('colTallaHM').innerHTML=h+'</tbody></table>';
}
