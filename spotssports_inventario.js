function getFilteredInvRows(){
  var f=gf();
  return (DATA.inv_rows||[]).filter(function(r){
    return(!_modelo||r.modelo===_modelo)&&(!f.tienda||r.ubicacion===f.tienda)&&(!f.genero||r.genero===f.genero)&&(!f.color||r.color===f.color);
  });
}

function rInventario(){
  var invRows=getFilteredInvRows();
  if(!invRows.length){
    document.getElementById('invSummary').innerHTML='<div class="nodata" style="grid-column:1/-1">Sin datos de inventario para los filtros seleccionados</div>';
    document.getElementById('invLocGrid').innerHTML='';
    return;
  }
  var tot=0,enTiendas=0,enTaller=0,byLoc={};
  invRows.forEach(function(r){
    tot+=r.qty;
    if(r.ubicacion==='TALLER')enTaller+=r.qty;else enTiendas+=r.qty;
    if(!byLoc[r.ubicacion])byLoc[r.ubicacion]={total:0,rows:{}};
    var rowKey=r.genero+' · '+r.color;
    if(!byLoc[r.ubicacion].rows[rowKey])byLoc[r.ubicacion].rows[rowKey]={genero:r.genero,color:r.color,tallas:{}};
    byLoc[r.ubicacion].rows[rowKey].tallas[r.talla]=(byLoc[r.ubicacion].rows[rowKey].tallas[r.talla]||0)+r.qty;
  });
  Object.keys(byLoc).forEach(function(loc){
    var ld=byLoc[loc],lt=0;
    Object.keys(ld.rows).forEach(function(rk){
      var rt=Object.values(ld.rows[rk].tallas).reduce(function(a,b){return a+b;},0);
      lt+=rt;
    });
    ld.total=lt;
  });
  document.getElementById('invSummary').innerHTML=
    '<div class="inv-sum-card"><div class="num">'+tot.toLocaleString()+'</div><div class="lbl">Stock Total</div></div>'+
    '<div class="inv-sum-card tiendas"><div class="num">'+enTiendas.toLocaleString()+'</div><div class="lbl">En Tiendas</div></div>'+
    '<div class="inv-sum-card taller"><div class="num">'+enTaller.toLocaleString()+'</div><div class="lbl">En Taller</div></div>';
  var locArr=Object.keys(byLoc).sort(function(a,b){
    if(a==='TALLER')return 1;if(b==='TALLER')return-1;
    return byLoc[b].total-byLoc[a].total;
  });
  var allTallas=sortTallaKeys(invRows.reduce(function(acc,r){if(acc.indexOf(r.talla)<0)acc.push(r.talla);return acc;},[]));
  var h='';
  locArr.forEach(function(loc){
    var ld=byLoc[loc];
    var rowKeys=Object.keys(ld.rows).sort(function(a,b){
      var sa=Object.values(ld.rows[a].tallas).reduce(function(x,y){return x+y;},0);
      var sb=Object.values(ld.rows[b].tallas).reduce(function(x,y){return x+y;},0);
      return sb-sa;
    });
    var isTaller=loc==='TALLER';
    h+='<div class="inv-loc-card"'+(isTaller?' style="border-color:#f9731644"':'')+'>'+
      '<div class="inv-loc-hdr">'+
      '<div><h4>'+(isTaller?'🏭 ':'🏬 ')+loc+'</h4><div class="sub2">Stock por género, color y talla</div></div>'+
      '<div class="inv-loc-tot" style="'+(isTaller?'color:#f97316':'')+'">'+ld.total+' und</div></div>'+
      '<div class="inv-matrix-wrap"><table class="inv-matrix"><thead><tr><th></th>'+
      allTallas.map(function(t){return'<th>'+t+'</th>';}).join('')+'</tr></thead><tbody>';
    rowKeys.forEach(function(rk){
      var rd=ld.rows[rk];
      h+='<tr><td class="color-cell"><span class="chip" style="background:'+cn(rd.color)+'"></span>'+(GICO[rd.genero]||'')+' '+rd.genero+' · '+rd.color+'</td>';
      allTallas.forEach(function(t){
        var v=rd.tallas[t]||0;
        h+='<td style="text-align:center">'+(v>0?'<span class="qty-pill">'+v+'</span>':'<span class="qty-empty">·</span>')+'</td>';
      });
      h+='</tr>';
    });
    h+='</tbody></table></div></div>';
  });
  document.getElementById('invLocGrid').innerHTML=h;
}