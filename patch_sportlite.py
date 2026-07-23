#!/usr/bin/env python3
"""Patch sportlite.html with new Excel data and BIOMOVE-style features."""
import json
import re
from build_sportlite_data import build

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open('/workspace/sportlite.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace DATA block
html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

dr = data['date_range']
html = re.sub(r'Nov 2025 — May 2026', dr, html)

# Inventory tab
html = html.replace(
    '<button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    '<button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>\n'
    '  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
)

inv_section = '''
<div class="sec" id="sec-inventario">
  <div class="inv-summary" id="invSummary"></div>
  <div class="inv-loc-grid" id="invLocGrid"></div>
</div>

<!-- DECISIONES -->'''
html = html.replace('<!-- DECISIONES -->', inv_section)

# CSS updates
html = html.replace(
    '.rk{font-family:var(--fh);font-weight:800;color:var(--ac);font-size:0.84rem}',
    '.rk{font-family:var(--fb);font-weight:600;color:var(--mu);font-size:0.62rem;letter-spacing:0.2px}',
)
html = html.replace(
    '.fbtn:hover{opacity:0.85}',
    '.fbtn:hover{opacity:0.85}\n.msel{background:var(--ac)!important;color:#fff!important;border-color:var(--ac)!important;font-weight:700}',
)
html = html.replace(
    '.tkpi .ts{font-size:0.68rem;color:var(--mu2);margin-top:1px}',
    '''.tkpi .ts{font-size:0.68rem;color:var(--mu2);margin-top:1px}
.inv-summary{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:14px}
@media(max-width:780px){.inv-summary{grid-template-columns:1fr}}
.inv-sum-card{background:var(--s2);border:1px solid var(--brd);border-radius:12px;padding:20px 16px;text-align:center}
.inv-sum-card .num{font-family:var(--fh);font-size:2rem;font-weight:800;line-height:1;color:var(--ac)}
.inv-sum-card .lbl{font-size:0.68rem;color:var(--mu);text-transform:uppercase;letter-spacing:0.6px;margin-top:6px}
.inv-sum-card.tiendas .num{color:#00bcd4}
.inv-sum-card.taller{border-color:#f9731644;background:rgba(249,115,22,.06)}
.inv-sum-card.taller .num{color:#f97316}
.inv-loc-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}
.inv-loc-card{background:var(--surf);border:1px solid var(--brd);border-radius:12px;padding:14px 16px}
.inv-loc-hdr{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:10px;gap:8px}
.inv-loc-hdr h4{font-family:var(--fh);font-size:0.82rem;font-weight:800;margin:0}
.inv-loc-hdr .sub2{font-size:0.64rem;color:var(--mu);margin-top:2px}
.inv-loc-tot{font-family:var(--fh);font-size:0.9rem;font-weight:800;color:var(--ac);white-space:nowrap}
.inv-matrix-wrap{overflow-x:auto;padding-bottom:4px}
.inv-matrix{border-collapse:separate;border-spacing:3px;width:100%}
.inv-matrix th{font-size:0.62rem;color:var(--mu);padding:2px 5px;text-align:center;font-weight:600;white-space:nowrap}
.inv-matrix .color-cell{text-align:left;font-size:0.71rem;white-space:nowrap;padding-right:8px;color:var(--tx);font-weight:500}
.inv-matrix .qty-pill{display:inline-block;background:var(--ac);color:#fff;border-radius:5px;padding:3px 8px;font-size:0.7rem;font-weight:700;min-width:24px;text-align:center}
.inv-matrix .qty-empty{color:var(--mu2);font-size:0.65rem}''',
)

# JS state and stores
html = html.replace("var _modelo='',_per='all',_theme='dark';", "var _modelo='',_selectedMeses=[],_theme='dark';")
html = html.replace(
    "var NEW_STORES=['MARGARITA','TOLON'];\nvar NEW_STORE_CAPS={'MARGARITA':{base:'GRIE',mult:2,label:'2× capacidad GRIE'},'TOLON':{base:'CHACAO',mult:1,label:'1× capacidad CHACAO'}};",
    "var NEW_STORES=['VELA'];\nvar NEW_STORE_CAPS={'VELA':{base:'GRIE',mult:1.5,label:'1.5× capacidad GRIE (La Grieta)'}};",
)

# Talla ordering helpers
html = html.replace(
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};",
    "var MODELO_ID={'MIKA SPORT LITE':'MIKA','NOAH SPORT LITE':'NOAH','MAYA SPORT LITE':'MAYA'};\n"
    "var TALLA_ORDER=['XS','S','M','L','XL','2XL','3XL'];\n"
    "function tallaIdx(t){var i=TALLA_ORDER.indexOf(t);return i>=0?i:999;}\n"
    "function sortTallas(items){return items.slice().sort(function(a,b){var ka=typeof a==='object'?a.k:a,kb=typeof b==='object'?b.k:b;return tallaIdx(ka)-tallaIdx(kb);});}\n"
    "function sortTallaKeys(keys){return keys.slice().sort(function(a,b){return tallaIdx(a)-tallaIdx(b);});}",
)

# Period filter
old_period = """function getMesesActivos(){var m=DATA.meses_order;if(_per==='all')return m;if(_per==='l1')return m.slice(-1);if(_per==='l2')return m.slice(-2);if(_per==='l3')return m.slice(-3);if(_per.indexOf('m:')==0)return[_per.slice(2)];return m;}
function buildPeriodBtns(){
  var m=DATA.meses_order,c=document.getElementById('periodBtns');if(!c)return;
  var btns=[{l:'Todo',p:'all'}];if(m.length>=2)btns.push({l:'Últ. mes',p:'l1'});if(m.length>=3)btns.push({l:'Últ. 2m',p:'l2'});if(m.length>=4)btns.push({l:'Últ. 3m',p:'l3'});
  for(var i=0;i<m.length;i++)btns.push({l:mlbl(m[i]),p:'m:'+m[i]});
  c.innerHTML=btns.map(function(b){var act=b.p==='all';return'<button data-p="'+b.p+'" onclick="setPer(this.dataset.p)" style="background:'+(act?'var(--ac)':'var(--s2)')+';color:'+(act?'#fff':'var(--mu)')+';border:1px solid '+(act?'var(--ac)':'var(--brd)')+';border-radius:20px;padding:3px 9px;font-size:0.66rem;cursor:pointer;font-family:var(--fb);white-space:nowrap">'+b.l+'</button>';}).join('');
}
function setPer(p){_per=p;document.querySelectorAll('#periodBtns button').forEach(function(b){var a=b.dataset.p===p;b.style.background=a?'var(--ac)':'var(--s2)';b.style.color=a?'#fff':'var(--mu)';b.style.borderColor=a?'var(--ac)':'var(--brd)';});af();}"""

new_period = """function getMesesActivos(){var m=DATA.meses_order;if(!_selectedMeses.length)return m;return _selectedMeses.slice().sort(function(a,b){return m.indexOf(a)-m.indexOf(b);});}
function buildPeriodBtns(){
  var m=DATA.meses_order,c=document.getElementById('periodBtns');if(!c)return;
  var h='<button data-p="all" onclick="togglePerAll()" style="background:'+(!_selectedMeses.length?'var(--ac)':'var(--s2)')+';color:'+(!_selectedMeses.length?'#fff':'var(--mu)')+';border:1px solid '+(!_selectedMeses.length?'var(--ac)':'var(--brd)')+';border-radius:20px;padding:3px 9px;font-size:0.66rem;cursor:pointer;font-family:var(--fb);white-space:nowrap;margin-right:4px">Todo</button>';
  for(var i=0;i<m.length;i++){var act=_selectedMeses.indexOf(m[i])>=0;h+='<button data-m="'+m[i]+'" onclick="togglePerMonth(this.dataset.m)" class="'+(act?'msel':'')+'" style="background:'+(act?'var(--ac)':'var(--s2)')+';color:'+(act?'#fff':'var(--mu)')+';border:1px solid '+(act?'var(--ac)':'var(--brd)')+';border-radius:20px;padding:3px 9px;font-size:0.66rem;cursor:pointer;font-family:var(--fb);white-space:nowrap">'+mlbl(m[i])+'</button>';}
  c.innerHTML=h;
}
function togglePerAll(){_selectedMeses=[];buildPeriodBtns();af();}
function togglePerMonth(mes){var i=_selectedMeses.indexOf(mes);if(i>=0)_selectedMeses.splice(i,1);else _selectedMeses.push(mes);buildPeriodBtns();af();}"""

html = html.replace(old_period, new_period)
html = html.replace(
    "var active=f.tienda||f.genero||f.color||_per!=='all'||_modelo;",
    "var active=f.tienda||f.genero||f.color||_selectedMeses.length||_modelo;",
)
html = html.replace(
    "filterModelButtons();setPer('all');",
    "filterModelButtons();_selectedMeses=[];buildPeriodBtns();af();",
)

# Stock helpers
stock_fn = """
function getFilteredStock(modelo,genero,color,tienda){
  var src={};
  if(tienda&&DATA.stock_by_loc&&DATA.stock_by_loc[tienda]){src=DATA.stock_by_loc[tienda];}
  else if(DATA.stock_by_loc){Object.keys(DATA.stock_by_loc).forEach(function(loc){Object.keys(DATA.stock_by_loc[loc]).forEach(function(k){src[k]=(src[k]||0)+DATA.stock_by_loc[loc][k];});});}
  else{src=DATA.stock||{};}
  var total=0;
  Object.keys(src).forEach(function(k){
    var parts=k.split('/');
    if((!modelo||parts[0]===modelo)&&(!genero||parts[1]===genero)&&(!color||parts[2]===color)) total+=(src[k]||0);
  });
  return total;
}
function getFilteredInvRows(){
  var f=gf();
  return (DATA.inv_rows||[]).filter(function(r){
    return(!_modelo||r.modelo===_modelo)&&(!f.tienda||r.ubicacion===f.tienda)&&(!f.genero||r.genero===f.genero)&&(!f.color||r.color===f.color);
  });
}

"""
html = html.replace('function updateKPIs(){', stock_fn + 'function updateKPIs(){')

old_stk = """  var gStk=0;
  if(_fColorSL||_fGenoSL){
    Object.keys(DATA.stock).forEach(function(k){
      var parts=k.split('/');
      var okM=!_modelo||parts[0]===_modelo;
      var okG=!_fGenoSL||parts[1]===_fGenoSL;
      var okC=!_fColorSL||parts[2]===_fColorSL;
      if(okM&&okG&&okC) gStk+=(DATA.stock[k]||0);
    });
  } else if(_modelo){
    gStk=DATA.stock_by_modelo[_modelo]||0;
  } else {
    Object.values(DATA.stock_by_modelo).forEach(function(v){gStk+=v;});
  }"""
new_stk = """  var _fTiendaSL=document.getElementById('fT')?document.getElementById('fT').value:'';
  var gStk=getFilteredStock(_modelo,_fGenoSL,_fColorSL,_fTiendaSL);"""
html = html.replace(old_stk, new_stk)

# Tabs
html = html.replace(
    "if(tx.indexOf('Tienda')>=0)return'tiendas';return'decisiones';}",
    "if(tx.indexOf('Tienda')>=0)return'tiendas';if(tx.indexOf('Inventario')>=0)return'inventario';return'decisiones';}",
)
html = html.replace(
    "var TABS=['resumen','colores','tallas','tiendas','decisiones'];",
    "var TABS=['resumen','colores','tallas','tiendas','inventario','decisiones'];",
)
html = html.replace(
    "else if(n==='decisiones')rDecisiones();",
    "else if(n==='inventario')rInventario();else if(n==='decisiones')rDecisiones();",
)

# Tallas sort
html = html.replace(
    "generos.forEach(function(g){var gRows=rows.filter(function(r){return r.genero===g;});var byT=ag(gRows,'talla');var col=gcol(g);",
    "generos.forEach(function(g){var gRows=rows.filter(function(r){return r.genero===g;});var byT=sortTallas(ag(gRows,'talla'));var col=gcol(g);",
)
html = html.replace(
    "var byColor=ag(rows,'color').slice(0,12),tallas=ag(rows,'talla').map(function(x){return x.k;});var m2=ag2(rows,'color','talla');",
    "var byColor=ag(rows,'color').slice(0,12),tallas=sortTallaKeys(ag(rows,'talla').map(function(x){return x.k;}));var m2=ag2(rows,'color','talla');",
)

# Tiendas ranking
html = html.replace(
    '<colgroup><col style="width:32px"><col style="width:110px">',
    '<colgroup><col style="width:24px"><col style="width:auto">',
)
html = html.replace(
    "rh+='<tr><td><span class=\"rk\">#'+(i+1)+'</span></td><td style=\"font-weight:600\">'+(isN?",
    "rh+='<tr><td><span class=\"rk\">#'+(i+1)+'</span></td><td style=\"font-weight:600;font-size:0.8rem\">'+(isN?",
)

# Decisiones stores (second occurrence)
html = html.replace(
    "var NEW_STORES=['MARGARITA','TOLON'];\nvar NEW_STORE_CAPS={'MARGARITA':{base:'GRIE',mult:2,label:'2\\xd7 capacidad GRIE'},'TOLON':{base:'CHACAO',mult:1,label:'1\\xd7 capacidad CHACAO'}};",
    "var NEW_STORES=['VELA'];\nvar NEW_STORE_CAPS={'VELA':{base:'GRIE',mult:1.5,label:'1.5\\xd7 capacidad GRIE (La Grieta)'}};",
)

# Reabast subtitle
html = html.replace(
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 MARGARITA proyectada: 2× velocidad GRIE · CERRO VERDE excluida de reabastecimiento</span></div>',
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 MARGARITA proyectada: 2× velocidad GRIE · VELA: 1.5× GRIE · CERRO VERDE excluida</span></div>',
)

# gStockSrc
html = html.replace(
    'function gColorStk(modelo,genero,color){\n  // Sum all tallas stock for this model/genero/color\n  var prefix=modelo+\'/\'+genero+\'/\'+color+\'/\';\n  var total=0;\n  Object.keys(DATA.stock).forEach(function(k){\n    if(k.indexOf(prefix)===0) total+=(DATA.stock[k]||0);\n  });\n  return total;\n}\nfunction gTallaStk(modelo,genero,color,talla){\n  return DATA.stock[modelo+\'/\'+genero+\'/\'+color+\'/\'+talla]||0;\n}',
    'function gStockSrc(){\n  var f=gf(),src={};\n  if(f.tienda&&DATA.stock_by_loc&&DATA.stock_by_loc[f.tienda]){src=DATA.stock_by_loc[f.tienda];}\n  else if(DATA.stock_by_loc){Object.keys(DATA.stock_by_loc).forEach(function(loc){Object.keys(DATA.stock_by_loc[loc]).forEach(function(k){src[k]=(src[k]||0)+DATA.stock_by_loc[loc][k];});});}\n  else{src=DATA.stock||{};}\n  return src;\n}\nfunction gColorStk(modelo,genero,color){\n  var prefix=modelo+\'/\'+genero+\'/\'+color+\'/\',total=0,src=gStockSrc();\n  Object.keys(src).forEach(function(k){if(k.indexOf(prefix)===0)total+=(src[k]||0);});\n  return total;\n}\nfunction gTallaStk(modelo,genero,color,talla){\n  return gStockSrc()[modelo+\'/\'+genero+\'/\'+color+\'/\'+talla]||0;\n}',
)

# renderReabast store list
html = html.replace(
    '  var storeList=ALL_STORES.concat(NEW_STORES);',
    '  var storeList=ALL_STORES.slice();\n  NEW_STORES.forEach(function(s){if(storeList.indexOf(s)<0)storeList.push(s);});',
)
html = html.replace(
    '    var isNew=NEW_STORES.indexOf(store)>=0;',
    '    var isNew=!!NEW_STORE_CAPS[store];',
)
html = html.replace(
    '        var sh=isNew?getNewStoreShare(store,sw.shares):sw.shares[store]||0;',
    '        var sh=isNew?getNewStoreShare(store,sw.shares):(sw.shares[store]||0);',
)

# rInventario
r_inv = """
function rInventario(){
  var invRows=getFilteredInvRows();
  if(!invRows.length){
    document.getElementById('invSummary').innerHTML='<div class="nodata" style="grid-column:1/-1">Sin datos de inventario</div>';
    document.getElementById('invLocGrid').innerHTML='';
    return;
  }
  var tot=0,enTiendas=0,enTaller=0,byLoc={};
  invRows.forEach(function(r){
    tot+=r.qty;
    if(r.ubicacion==='TALLER')enTaller+=r.qty;else enTiendas+=r.qty;
    if(!byLoc[r.ubicacion])byLoc[r.ubicacion]={total:0,colors:{}};
    byLoc[r.ubicacion].total+=r.qty;
    if(!byLoc[r.ubicacion].colors[r.color])byLoc[r.ubicacion].colors[r.color]={};
    byLoc[r.ubicacion].colors[r.color][r.talla]=(byLoc[r.ubicacion].colors[r.color][r.talla]||0)+r.qty;
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
    var colors=Object.keys(ld.colors).sort(function(a,b){
      var sa=Object.values(ld.colors[a]).reduce(function(x,y){return x+y;},0);
      var sb=Object.values(ld.colors[b]).reduce(function(x,y){return x+y;},0);
      return sb-sa;
    });
    var isTaller=loc==='TALLER';
    h+='<div class="inv-loc-card"'+(isTaller?' style="border-color:#f9731644"':'')+'>'+
      '<div class="inv-loc-hdr">'+
      '<div><h4>'+(isTaller?'🔧 ':'🏪 ')+loc+'</h4><div class="sub2">Stock por color y talla</div></div>'+
      '<div class="inv-loc-tot" style="'+(isTaller?'color:#f97316':'')+'">'+ld.total+' und</div></div>'+
      '<div class="inv-matrix-wrap"><table class="inv-matrix"><thead><tr><th></th>'+
      allTallas.map(function(t){return'<th>'+t+'</th>';}).join('')+'</tr></thead><tbody>';
    colors.forEach(function(col){
      h+='<tr><td class="color-cell"><span class="chip" style="background:'+cn(col)+'"></span>'+col+'</td>';
      allTallas.forEach(function(t){
        var v=ld.colors[col][t]||0;
        h+='<td style="text-align:center">'+(v?'<span class="qty-pill">'+v+'</span>':'<span class="qty-empty">·</span>')+'</td>';
      });
      h+='</tr>';
    });
    h+='</tbody></table></div></div>';
  });
  document.getElementById('invLocGrid').innerHTML=h;
}

"""
html = html.replace('// ── DECISIONES ──', r_inv + '\n// ── DECISIONES ──')

with open('/workspace/sportlite.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('sportlite.html updated')
print(f'  Sales: {len(data["raw_rows"])} rows, {data["total"]} units')
print(f'  Stock: {data["stock_total"]} units')
print(f'  Range: {data["date_range"]}')
