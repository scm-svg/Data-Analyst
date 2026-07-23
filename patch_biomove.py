#!/usr/bin/env python3
"""Patch BIOMOVE.html with new data and features."""
import json
import re
from build_biomove_data import build

data = build()
data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

with open('/workspace/BIOMOVE.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace DATA block
html = re.sub(
    r'var DATA=\{.*?\};\nvar _modelo',
    f'var DATA={data_json};\nvar _modelo',
    html,
    count=1,
    flags=re.DOTALL,
)

# Date range
dr = data['date_range']
html = html.replace('Oct 2025 — Abr 2026', dr)

# Add Running Tank button after Helen button
html = html.replace(
    '<button class="mbtn" data-m="HELEN BIO MOVE" onclick="setModelo(\'HELEN BIO MOVE\')">🏃 Helen <span class="mcnt" id="mcnt_HELEN">0</span></button>\n</div>',
    '<button class="mbtn" data-m="HELEN BIO MOVE" onclick="setModelo(\'HELEN BIO MOVE\')">🏃 Helen <span class="mcnt" id="mcnt_HELEN">0</span></button>\n'
    '  <button class="mbtn" data-m="RUNNING TANK BIO MOVE" onclick="setModelo(\'RUNNING TANK BIO MOVE\')">🏃 Running Tank <span class="mcnt" id="mcnt_RUNNING_TANK">0</span></button>\n</div>',
)

# Add Inventario tab
html = html.replace(
    '<button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
    '<button class="tab" onclick="st(\'inventario\')">📦 Inventario</button>\n'
    '  <button class="tab" onclick="st(\'decisiones\')">💡 Decisiones</button>',
)

# Add Inventario section before DECISIONES
inv_section = '''
<div class="sec" id="sec-inventario">
  <div class="tkpis" id="invKpis"></div>
  <div class="g2">
    <div class="card"><h3>📍 Stock por Ubicación</h3><div class="sub">Unidades en inventario por punto</div><div class="cw t"><canvas id="cInvLoc"></canvas></div></div>
    <div class="card"><h3>🏷️ Stock por Modelo</h3><div class="sub">Distribución de inventario</div><div class="cw"><canvas id="cInvMod"></canvas></div></div>
  </div>
  <div class="g1 card">
    <h3>📋 Detalle de Inventario</h3>
    <div class="sub">SKU · Modelo · Color · Talla · Cantidad</div>
    <div class="cscroll" style="max-height:420px"><table class="ct"><thead><tr><th>Ubicación</th><th>SKU</th><th>Modelo</th><th>Género</th><th>Color</th><th>Talla</th><th style="text-align:right">Cant.</th></tr></thead><tbody id="invBody"></tbody></table></div>
  </div>
  <div class="g1 card"><h3>Color × Ubicación</h3><div class="sub">Heatmap de inventario</div><div class="hmw" id="invColorHM"></div></div>
</div>

<!-- DECISIONES -->'''

html = html.replace('<!-- DECISIONES -->', inv_section)

# Update reabastecimiento subtitle
html = html.replace(
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 MARGARITA (2× GRIE) y TOLON (1× CHACAO) son tiendas nuevas proyectadas</span></div>',
    '<div class="sub">Distribución sugerida · <span style="color:#f97316">🆕 VELA proyectada como 1.5× La Grieta (GRIE)</span></div>',
)

# Add multi-select month styles after period button styles
html = html.replace(
    '.fbtn:hover{opacity:0.85}',
    '.fbtn:hover{opacity:0.85}\n.msel{background:var(--ac)!important;color:#fff!important;border-color:var(--ac)!important;font-weight:700}',
)

# Replace JS constants and functions
js_patches = [
    # Model icons and IDs
    (
        "var MICO={'DOMINIC BIO MOVE':'🏃','HELEN BIO MOVE':'🏃'};",
        "var MICO={'DOMINIC BIO MOVE':'🏃','HELEN BIO MOVE':'🏃','RUNNING TANK BIO MOVE':'🏃'};",
    ),
    (
        "var MODELO_ID={'DOMINIC BIO MOVE':'DOMINIC','HELEN BIO MOVE':'HELEN'};",
        "var MODELO_ID={'DOMINIC BIO MOVE':'DOMINIC','HELEN BIO MOVE':'HELEN','RUNNING TANK BIO MOVE':'RUNNING_TANK'};",
    ),
  # NEW_STORES
    (
        "var NEW_STORES=['MARGARITA','TOLON'];\nvar NEW_STORE_CAPS={'MARGARITA':{base:'GRIE',mult:2,label:'2× capacidad GRIE'},'TOLON':{base:'CHACAO',mult:1,label:'1× capacidad CHACAO'}};",
        "var NEW_STORES=['VELA'];\nvar NEW_STORE_CAPS={'VELA':{base:'GRIE',mult:1.5,label:'1.5× capacidad GRIE (La Grieta)'}};",
    ),
    # Title names
    (
        "var sn={'DOMINIC BIO MOVE':'Dominic','HELEN BIO MOVE':'Helen'};",
        "var sn={'DOMINIC BIO MOVE':'Dominic','HELEN BIO MOVE':'Helen','RUNNING TANK BIO MOVE':'Running Tank'};",
    ),
    # Period state
    (
        "var _modelo='',_per='all',_theme='dark';",
        "var _modelo='',_selectedMeses=[],_theme='dark';",
    ),
]

for old, new in js_patches:
    html = html.replace(old, new)

# Replace getMesesActivos and period functions
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

# Update af() active filter check
html = html.replace(
    "var active=f.tienda||f.genero||f.color||_per!=='all'||_modelo;",
    "var active=f.tienda||f.genero||f.color||_selectedMeses.length||_modelo;",
)

# Update rf() reset
html = html.replace(
    "filterModelButtons();setPer('all');",
    "filterModelButtons();_selectedMeses=[];buildPeriodBtns();",
)

# Update updateKPIs stock calculation
old_stk = """  var gStk=0;
  if(_fColorBM||_fGenoBM){
    Object.keys(DATA.stock).forEach(function(k){
      var parts=k.split('/');
      var okM=!_modelo||parts[0]===_modelo;
      var okG=!_fGenoBM||parts[1]===_fGenoBM;
      var okC=!_fColorBM||parts[2]===_fColorBM;
      if(okM&&okG&&okC) gStk+=(DATA.stock[k]||0);
    });
  } else if(_modelo){
    gStk=DATA.stock_by_modelo[_modelo]||0;
  } else {
    Object.values(DATA.stock_by_modelo).forEach(function(v){gStk+=v;});
  }"""

new_stk = """  var _fTiendaBM=document.getElementById('fT')?document.getElementById('fT').value:'';
  var gStk=getFilteredStock(_modelo,_fGenoBM,_fColorBM,_fTiendaBM);"""

html = html.replace(old_stk, new_stk)

# Add getFilteredStock and rInventario before updateKPIs
stock_fn = """
function getFilteredStock(modelo,genero,color,tienda){
  var src={};
  if(tienda&&DATA.stock_by_loc&&DATA.stock_by_loc[tienda]){
    src=DATA.stock_by_loc[tienda];
  } else if(DATA.stock_by_loc){
    Object.keys(DATA.stock_by_loc).forEach(function(loc){
      Object.keys(DATA.stock_by_loc[loc]).forEach(function(k){
        src[k]=(src[k]||0)+DATA.stock_by_loc[loc][k];
      });
    });
  } else {
    src=DATA.stock||{};
  }
  var total=0;
  Object.keys(src).forEach(function(k){
    var parts=k.split('/');
    var okM=!modelo||parts[0]===modelo;
    var okG=!genero||parts[1]===genero;
    var okC=!color||parts[2]===color;
    if(okM&&okG&&okC) total+=(src[k]||0);
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

# Update aTab and TABS and rs
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

# Update decisiones NEW_STORES (second occurrence)
html = html.replace(
    "var NEW_STORES=['MARGARITA','TOLON'];\nvar NEW_STORE_CAPS={'MARGARITA':{base:'GRIE',mult:2,label:'2\\xd7 capacidad GRIE'},'TOLON':{base:'CHACAO',mult:1,label:'1\\xd7 capacidad CHACAO'}};",
    "var NEW_STORES=['VELA'];\nvar NEW_STORE_CAPS={'VELA':{base:'GRIE',mult:1.5,label:'1.5\\xd7 capacidad GRIE (La Grieta)'}};",
)

# Add rInventario function before DECISIONES section comment in JS
r_inv = """
function rInventario(){
  var invRows=getFilteredInvRows();
  if(!invRows.length){
    document.getElementById('invKpis').innerHTML='<div class="nodata" style="grid-column:1/-1">Sin datos de inventario</div>';
    document.getElementById('invBody').innerHTML='<tr><td colspan="7" class="nodata">Sin datos</td></tr>';
    return;
  }
  var byLoc={},byMod={},byCol={};
  invRows.forEach(function(r){
    byLoc[r.ubicacion]=(byLoc[r.ubicacion]||0)+r.qty;
    byMod[r.modelo]=(byMod[r.modelo]||0)+r.qty;
    if(!byCol[r.color])byCol[r.color]={};
    byCol[r.color][r.ubicacion]=(byCol[r.color][r.ubicacion]||0)+r.qty;
  });
  var locArr=Object.entries(byLoc).sort(function(a,b){return b[1]-a[1];});
  var modArr=Object.entries(byMod).sort(function(a,b){return b[1]-a[1];});
  var tot=invRows.reduce(function(a,r){return a+r.qty;},0);
  document.getElementById('invKpis').innerHTML=locArr.map(function(kv){
    var pct=tot>0?Math.round(kv[1]/tot*1000)/10:0;
    var isN=NEW_STORES.indexOf(kv[0])>=0;
    return'<div class="tkpi" style="'+(isN?'border-color:#f97316;':'')+'"><div class="tv" style="color:'+(isN?'#f97316':'var(--ac)')+'">'+kv[1]+'</div><div class="tl">'+(isN?'🆕 ':'')+kv[0]+'</div><div class="ts">'+pct+'%</div></div>';
  }).join('');
  mc('cInvLoc','bar',{labels:locArr.map(function(x){return x[0];}),datasets:[{data:locArr.map(function(x){return x[1];}),backgroundColor:locArr.map(function(x,i){return PAL[i%PAL.length]+'bb';}),borderColor:locArr.map(function(x,i){return PAL[i%PAL.length];}),borderWidth:1,borderRadius:6}]},Object.assign(bo(),{plugins:{legend:{display:false},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:12},textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.7)',anchor:'end',align:'start',formatter:function(v){return v;}}}}));
  mc('cInvMod','doughnut',{labels:modArr.map(function(x){return x[0];}),datasets:[{data:modArr.map(function(x){return x[1];}),backgroundColor:modArr.map(function(x,i){return PAL[i%PAL.length];}),borderWidth:1.5}]},Object.assign(bo(),{plugins:{legend:{display:true,position:'right',labels:{color:txCol(),font:{family:'DM Sans',size:10},boxWidth:10,padding:6}},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:11},formatter:function(v,ctx){var d=ctx.chart.data.datasets[0].data,t=d.reduce(function(a,b){return a+b;},0);return t>0?Math.round(v/t*100)+'%':'';}}},scales:{x:{display:false},y:{display:false}}}));
  var sorted=invRows.slice().sort(function(a,b){return b.qty-a.qty||a.ubicacion.localeCompare(b.ubicacion);});
  document.getElementById('invBody').innerHTML=sorted.map(function(r){
    return'<tr><td style="font-weight:600">'+r.ubicacion+'</td><td style="font-size:0.7rem;color:var(--mu)">'+r.sku+'</td><td>'+r.modelo.replace(' BIO MOVE','')+'</td><td>'+r.genero+'</td><td><span class="chip" style="background:'+cn(r.color)+'"></span>'+r.color+'</td><td style="font-weight:700">'+r.talla+'</td><td style="text-align:right;font-family:var(--fh);font-weight:800;color:#ffc107">'+r.qty+'</td></tr>';
  }).join('');
  var locs=locArr.map(function(x){return x[0];});
  var cols=Object.keys(byCol).sort(function(a,b){var sa=Object.values(byCol[a]).reduce(function(x,y){return x+y;},0);var sb=Object.values(byCol[b]).reduce(function(x,y){return x+y;},0);return sb-sa;}).slice(0,12);
  var mx=0;cols.forEach(function(c){locs.forEach(function(l){var v=(byCol[c]&&byCol[c][l])||0;if(v>mx)mx=v;});});
  var hh='<table class="hmt"><thead><tr><th></th>'+locs.map(function(l){return'<th>'+l+'</th>';}).join('')+'</tr></thead><tbody>';
  cols.forEach(function(c){
    hh+='<tr><td class="rl"><span class="chip" style="background:'+cn(c)+'"></span>'+c+'</td>';
    locs.forEach(function(l){var v=(byCol[c]&&byCol[c][l])||0;hh+='<td style="background:'+hb(v,mx)+';color:'+ht(v,mx)+'" title="'+c+' · '+l+': '+v+' und">'+v+'</td>';});
    hh+='</tr>';
  });
  document.getElementById('invColorHM').innerHTML=hh+'</tbody></table>';
}

"""

html = html.replace('// ── DECISIONES ──', r_inv + '\n// ── DECISIONES ──')

# Update gColorStk and gTallaStk to use filtered stock source
html = html.replace(
    'function gColorStk(modelo,genero,color){\n  // Sum all tallas stock for this model/genero/color\n  var prefix=modelo+\'/\'+genero+\'/\'+color+\'/\';\n  var total=0;\n  Object.keys(DATA.stock).forEach(function(k){\n    if(k.indexOf(prefix)===0) total+=(DATA.stock[k]||0);\n  });\n  return total;\n}\nfunction gTallaStk(modelo,genero,color,talla){\n  return DATA.stock[modelo+\'/\'+genero+\'/\'+color+\'/\'+talla]||0;\n}',
    'function gStockSrc(){\n  var f=gf(),src={};\n  if(f.tienda&&DATA.stock_by_loc&&DATA.stock_by_loc[f.tienda]){src=DATA.stock_by_loc[f.tienda];}\n  else if(DATA.stock_by_loc){Object.keys(DATA.stock_by_loc).forEach(function(loc){Object.keys(DATA.stock_by_loc[loc]).forEach(function(k){src[k]=(src[k]||0)+DATA.stock_by_loc[loc][k];});});}\n  else{src=DATA.stock||{};}\n  return src;\n}\nfunction gColorStk(modelo,genero,color){\n  var prefix=modelo+\'/\'+genero+\'/\'+color+\'/\',total=0,src=gStockSrc();\n  Object.keys(src).forEach(function(k){if(k.indexOf(prefix)===0)total+=(src[k]||0);});\n  return total;\n}\nfunction gTallaStk(modelo,genero,color,talla){\n  return gStockSrc()[modelo+\'/\'+genero+\'/\'+color+\'/\'+talla]||0;\n}',
)

with open('/workspace/BIOMOVE.html', 'w', encoding='utf-8') as f:
    f.write(html)

print('BIOMOVE.html updated successfully')
print(f'  Sales rows: {len(data["raw_rows"])}')
print(f'  Stock total: {data["stock_total"]}')
print(f'  Date range: {data["date_range"]}')
