function rTallas(){
  var rows=fr();
  if(!rows.length){
    document.getElementById('tallasGrid').innerHTML='<div class="nodata">Sin datos</div>';
    document.getElementById('colTallaHM').innerHTML='';
    return;
  }
  var salesMap={};
  rows.forEach(function(r){salesMap[r.color]=(salesMap[r.color]||0)+r.v;});
  var invMap={};
  (DATA.inv_rows||[]).forEach(function(r){
    if(_modelo&&r.modelo!==_modelo)return;
    invMap[r.color]=(invMap[r.color]||0)+r.qty;
  });
  var colors=sortColorKeys(Object.keys(salesMap).concat(Object.keys(invMap)));
  var grid=document.getElementById('tallasGrid');
  grid.style.cssText='display:grid;grid-template-columns:1fr;gap:14px;margin-bottom:14px';
  grid.innerHTML='<div class="card"><h3 style="color:var(--ac)">🎨 Diseños Eco Bag</h3><div class="sub">Incluye diseños con 0 ventas (rojo)</div><div class="cw"><canvas id="cTalla_UNI"></canvas></div></div>';
  var units=colors.map(function(c){return salesMap[c]||0;});
  var tot=units.reduce(function(a,b){return a+b;},0)||1;
  var pcts=units.map(function(v){return Math.round(v/tot*1000)/10;});
  mc('cTalla_UNI','bar',{labels:colors,datasets:[{data:pcts,backgroundColor:colors.map(function(c,u){return(units[u]===0?'#ef4444':cn(c))+'bb';}),borderColor:colors.map(function(c,u){return units[u]===0?'#ef4444':cn(c);}),borderWidth:1,borderRadius:5,_units:units}]},Object.assign(bo(),{plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e1f2b',borderColor:'#2a2b3a',borderWidth:1,titleFont:{family:'Syne',weight:'bold'},bodyFont:{family:'DM Sans'},padding:10,callbacks:{label:function(ctx){var u=ctx.dataset._units[ctx.dataIndex];return u>0?(' '+ctx.parsed.y.toFixed(1)+'%  ('+u+' und)'):' Sin ventas (0 und)';}}},datalabels:{display:true,color:function(ctx){return ctx.dataset._units[ctx.dataIndex]===0?'#ef4444':'#fff';},font:{family:'Syne',weight:'bold',size:10},anchor:'end',align:'start',formatter:function(v,ctx){var u=ctx.dataset._units[ctx.dataIndex];return u>0?v.toFixed(1)+'%':'0';}}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:9},maxRotation:45,minRotation:25}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11},callback:function(v){return v+'%';}},max:Math.min(100,Math.ceil((Math.max.apply(null,pcts.concat([0]))||100)*1.2/5)*5)||100}}}));
  var tiendas=ag(rows,'tienda').map(function(x){return x.k;});
  var m2=ag2(rows,'color','tienda');var mx=0;
  colors.forEach(function(c){tiendas.forEach(function(t){var v=(m2[c]&&m2[c][t])||0;if(v>mx)mx=v;});});
  var h='<table class="hmt"><thead><tr><th></th>'+tiendas.map(function(t){return'<th>'+t+'</th>';}).join('')+'</tr></thead><tbody>';
  colors.forEach(function(c){
    h+='<tr><td class="rl"><span class="chip" style="background:'+cn(c)+'"></span>'+c+'</td>'+
      tiendas.map(function(t){var v=(m2[c]&&m2[c][t])||0;return'<td style="background:'+(v?hb(v,mx):'#16171f')+';color:'+(v?ht(v,mx):'#ef4444')+'" title="'+c+' · '+t+': '+(v||0)+' und">'+(v||'0')+'</td>';}).join('')+'</tr>';
  });
  document.getElementById('colTallaHM').innerHTML=h+'</tbody></table>';
}

function sortColorKeys(keys){
  var u=[],seen={};
  keys.forEach(function(k){if(k&&!seen[k]){seen[k]=1;u.push(k);}});
  return u.sort();
}
