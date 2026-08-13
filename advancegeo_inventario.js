function getFilteredInvRows(){
  var f=gf();
  return (DATA.inv_rows||[]).filter(function(r){
    return(!_modelo||r.modelo===_modelo)&&(!f.tienda||r.ubicacion===f.tienda)&&(!f.genero||r.genero===f.genero)&&(!f.color||r.color===f.color);
  });
}

function salesSkuMap(){
  var f=gf(),mA=getMesesActivos(),map={};
  DATA.raw_rows.forEach(function(r){
    if(_modelo&&r.modelo!==_modelo)return;
    if(f.tienda&&r.tienda!==f.tienda)return;
    if(f.genero&&r.genero!==f.genero)return;
    if(f.color&&r.color!==f.color)return;
    if(mA.indexOf(r.mes)<0)return;
    var k=r.color+'/'+r.talla;
    map[k]=(map[k]||0)+r.v;
  });
  return map;
}

function rInventario(){
  var invRows=getFilteredInvRows();
  if(!invRows.length){
    document.getElementById('invSummary').innerHTML='<div class="nodata" style="grid-column:1/-1">Sin datos de inventario para los filtros seleccionados</div>';
    document.getElementById('invLocGrid').innerHTML='';
    return;
  }
  var salesMap=salesSkuMap();
  var tot=0,enTiendas=0,enTaller=0,byLoc={};
  invRows.forEach(function(r){
    tot+=r.qty;
    if(r.ubicacion==='TALLER')enTaller+=r.qty;else enTiendas+=r.qty;
    if(!byLoc[r.ubicacion])byLoc[r.ubicacion]={total:0,items:{}};
    var k=r.color+'/'+r.talla;
    byLoc[r.ubicacion].items[k]=(byLoc[r.ubicacion].items[k]||0)+r.qty;
  });
  Object.keys(byLoc).forEach(function(loc){
    byLoc[loc].total=Object.values(byLoc[loc].items).reduce(function(a,b){return a+b;},0);
  });
  document.getElementById('invSummary').innerHTML=
    '<div class="inv-sum-card"><div class="num">'+tot.toLocaleString()+'</div><div class="lbl">Stock Total</div></div>'+
    '<div class="inv-sum-card tiendas"><div class="num">'+enTiendas.toLocaleString()+'</div><div class="lbl">En Tiendas</div></div>'+
    '<div class="inv-sum-card taller"><div class="num">'+enTaller.toLocaleString()+'</div><div class="lbl">En Taller PT</div></div>';
  var TORD={'XS':0,'S':1,'M':2,'L':3,'XL':4,'2XL':5,'3XL':6};
  var locArr=Object.keys(byLoc).sort(function(a,b){
    if(a==='TALLER')return 1;if(b==='TALLER')return-1;
    return byLoc[b].total-byLoc[a].total;
  });
  var h='';
  locArr.forEach(function(loc){
    var ld=byLoc[loc];
    var keys=Object.keys(ld.items).sort(function(a,b){
      var ca=a.split('/')[0],cb=b.split('/')[0],ta=a.split('/')[1]||'',tb=b.split('/')[1]||'';
      if(ca!==cb)return ca.localeCompare(cb);
      return(TORD[ta]||99)-(TORD[tb]||99);
    });
    var isTaller=loc==='TALLER';
    h+='<div class="inv-loc-card"'+(isTaller?' style="border-color:#f9731644"':'')+'>'+
      '<div class="inv-loc-hdr">'+
      '<div><h4>'+(isTaller?'🏭 ':'🏬 ')+loc+'</h4><div class="sub2">Color × Talla · <span style="color:#ef4444">rojo = sin ventas en el período</span></div></div>'+
      '<div class="inv-loc-tot" style="'+(isTaller?'color:#f97316':'')+'">'+ld.total+' und</div></div>'+
      '<div class="inv-matrix-wrap"><table class="inv-matrix"><thead><tr><th>Color / Talla</th><th>Und</th><th>Ventas</th></tr></thead><tbody>';
    keys.forEach(function(k){
      var parts=k.split('/');
      var col=parts[0],talla=parts.slice(1).join('/')||'';
      var v=ld.items[k]||0;
      var sv=salesMap[k]||0;
      var nomove=v>0&&sv===0;
      h+='<tr><td class="color-cell"><span class="chip" style="background:'+cn(col)+'"></span>'+col+' <span style="color:var(--mu);font-weight:600">'+talla+'</span></td>'+
        '<td style="text-align:center">'+(v>0?'<span class="qty-pill'+(nomove?' nomove':'')+'">'+v+'</span>':'<span class="qty-empty">0</span>')+'</td>'+
        '<td style="text-align:center"><span class="qty-ventas'+(nomove?' zero':'')+'">'+(sv>0?(sv+' und'):'0 und')+'</span></td></tr>';
    });
    h+='</tbody></table></div></div>';
  });
  document.getElementById('invLocGrid').innerHTML=h;
}
