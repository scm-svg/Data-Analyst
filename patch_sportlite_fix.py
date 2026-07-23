#!/usr/bin/env python3
"""Patch sportlite.html from working base with safe BIOMOVE-style changes."""
from pathlib import Path
import re

path = Path("sportlite.html")
html = path.read_text(encoding="utf-8")

# 1) Remove partial-month alert
html = html.replace(
    "  if(DATA.es_parcial)alerts.push({type:'info',text:'📅 Mayo 2026 con datos parciales'});\n",
    "",
)

# 2) Fix tallas chart Y-axis using real max (keep mc() on its own line)
old_tallas = """  generos.forEach(function(g){var gRows=rows.filter(function(r){return r.genero===g;});var byT=sortTallas(ag(gRows,'talla'));var col=gcol(g);
    mc('cTalla_'+g,'bar',{labels:byT.map(function(x){return x.k;}),datasets:[{data:byT.map(function(x){return x.pct;}),backgroundColor:col+'bb',borderColor:col,borderWidth:1,borderRadius:5,_units:byT.map(function(x){return x.v;})}]},Object.assign(bo(),{plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e1f2b',borderColor:'#2a2b3a',borderWidth:1,titleFont:{family:'Syne',weight:'bold'},bodyFont:{family:'DM Sans'},padding:10,callbacks:{title:function(items){return 'Talla '+items[0].label;},label:function(ctx){return ' '+ctx.parsed.y.toFixed(1)+'%  ('+ctx.dataset._units[ctx.dataIndex]+' und)';}}},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:12},textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.7)',anchor:'end',align:'start',formatter:function(v){return v.toFixed(1)+'%';}}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11},callback:function(v){return v+'%';}},max:Math.min(100,Math.ceil((byT[0]?byT[0].pct:100)*1.3/5)*5)}}}));"""

new_tallas = """  generos.forEach(function(g){
    var gRows=rows.filter(function(r){return r.genero===g;});
    var byT=sortTallas(ag(gRows,'talla'));
    var col=gcol(g);
    var yMax=Math.min(100,Math.ceil(byT.reduce(function(m,x){return Math.max(m,x.pct);},0)*1.15/5)*5);
    mc('cTalla_'+g,'bar',{labels:byT.map(function(x){return x.k;}),datasets:[{data:byT.map(function(x){return x.pct;}),backgroundColor:col+'bb',borderColor:col,borderWidth:1,borderRadius:5,_units:byT.map(function(x){return x.v;})}]},Object.assign(bo(),{plugins:{legend:{display:false},tooltip:{backgroundColor:'#1e1f2b',borderColor:'#2a2b3a',borderWidth:1,titleFont:{family:'Syne',weight:'bold'},bodyFont:{family:'DM Sans'},padding:10,callbacks:{title:function(items){return 'Talla '+items[0].label;},label:function(ctx){return ' '+ctx.parsed.y.toFixed(1)+'%  ('+ctx.dataset._units[ctx.dataIndex]+' und)';}}},datalabels:{display:true,color:'#fff',font:{family:'Syne',weight:'bold',size:12},textShadowBlur:3,textShadowColor:'rgba(0,0,0,0.7)',anchor:'end',align:'start',formatter:function(v){return v.toFixed(1)+'%';}}},scales:{x:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11}}},y:{grid:{color:'rgba(255,255,255,.04)'},ticks:{color:'#7a7b95',font:{family:'DM Sans',size:11},callback:function(v){return v+'%';}},max:yMax}}}));"""

if old_tallas not in html:
    raise SystemExit("tallas block not found")
html = html.replace(old_tallas, new_tallas)

# 3) Replace rDecisiones with BIOMOVE-style version
new_rdecisiones = r'''function rDecisiones(){
  var meses=_decMeses||2;
  var allRows=DATA.raw_rows;
  var filteredRows=allRows.filter(function(r){return(!_modelo||r.modelo===_modelo);});
  var modelos=ag(filteredRows,'modelo').map(function(x){return x.k;});
  var pgEl=document.getElementById('propGrid');if(!pgEl)return;pgEl.innerHTML='';

  modelos.forEach(function(modelo){
    var modRows=allRows.filter(function(r){return r.modelo===modelo;});
    var generos=ag(modRows,'genero').map(function(x){return x.k;});
    var cards=generos.map(function(genero){
      var lRows=modRows.filter(function(r){return r.genero===genero;});
      var lt=lRows.reduce(function(a,r){return a+r.v;},0);if(!lt)return'';
      var lineFc=getLF(genero,meses,modelo);
      var cM={};lRows.forEach(function(r){cM[r.color]=(cM[r.color]||0)+r.v;});
      var cA=Object.entries(cM).sort(function(a,b){return b[1]-a[1];});
      var lProd=0;
      var bars=cA.map(function(ce){
        var col=ce[0],colV=ce[1],pct=lt>0?Math.round(colV/lt*1000)/10:0;
        var cUid='pg_'+modelo.replace(/\W/g,'_')+'_'+genero+'_'+col.replace(/\W/g,'_');
        var tM={};lRows.filter(function(r){return r.color===col;}).forEach(function(r){tM[r.talla]=(tM[r.talla]||0)+r.v;});
        var tA=Object.entries(tM).sort(function(a,b){return b[1]-a[1];});
        var cNS=0;
        var cColorStk=gColorStk(modelo,genero,col);
        var det=tA.map(function(tv){
          var tSug=calcProp(tv[1],lt,lineFc);cNS+=tSug;lProd+=tSug;
          var tStk=gTallaStk(modelo,genero,col,tv[0]);
          return makeRow(tv[0],col,tv[1],colV,tSug,tStk);
        }).join('');
        return '<div style="margin-bottom:7px">'+
          '<div data-pguid="'+cUid+'" style="display:flex;align-items:center;gap:7px;cursor:pointer;padding:4px 5px;border-radius:6px">'+
          '<span style="width:9px;height:9px;border-radius:50%;background:'+cn(col)+';flex-shrink:0;border:1.5px solid rgba(255,255,255,.15)"></span>'+
          '<div style="font-size:0.73rem;font-weight:600;color:#e0e0f5;width:95px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+col+'</div>'+
          '<div style="flex:1;background:var(--s3);border-radius:3px;height:10px;overflow:hidden;position:relative"><div style="height:10px;border-radius:3px;background:'+cn(col)+';width:'+pct+'%"></div><span style="position:absolute;left:5px;top:0;line-height:10px;font-size:0.62rem;font-weight:700;color:#fff;text-shadow:0 0 3px rgba(0,0,0,.9)">'+pct+'%</span></div>'+
          '<div style="color:#86efac;font-weight:700;font-size:0.7rem;width:44px;text-align:right">'+cNS+'u</div>'+
          (cColorStk>0?'<div style="background:rgba(255,193,7,.15);border:1px solid #ffc10766;border-radius:5px;padding:1px 6px;color:#ffc107;font-size:0.62rem;font-weight:700;white-space:nowrap">📦'+cColorStk+'</div>':'')+
          '<span style="color:var(--ac);font-size:0.62rem;width:10px">&#9658;</span></div>'+
          '<div id="'+cUid+'" style="display:none;margin:2px 0 0 16px;padding:5px 7px;background:var(--s2);border-radius:5px;border-left:2px solid '+cn(col)+'44">'+
          '<div style="font-size:0.59rem;color:var(--mu2);margin-bottom:3px;font-weight:600">TALLA &middot; % &middot; HIST &middot; PROD &middot; <span style="color:#ffc107">STK</span></div>'+det+'</div></div>';
      }).join('');
      return '<div style="background:var(--s2);border-radius:10px;padding:13px;margin-bottom:8px">'+
        '<div style="font-family:var(--fh);font-size:0.79rem;font-weight:800;color:var(--a2);margin-bottom:2px">'+(GICO[genero]||'')+' '+genero+' <span style="font-size:0.67rem;font-weight:400;color:var(--mu)">(orden '+lineFc+' und/mes)</span></div>'+
        '<div style="font-size:0.65rem;color:var(--mu2);margin-bottom:8px">&#127981; Producir: <strong style="color:#86efac">'+lProd+'</strong> und</div>'+bars+'</div>';
    }).filter(Boolean).join('');
    if(!cards)return;
    pgEl.innerHTML+='<div style="background:var(--surf);border:1px solid var(--brd);border-radius:12px;padding:14px">'+
      '<div style="font-family:var(--fh);font-size:0.9rem;font-weight:800;color:var(--ac);margin-bottom:10px">'+(MICO[modelo]||'')+' '+modelo+'</div>'+cards+'</div>';
  });
  renderReabast(allRows);
}'''

start = html.index("function rDecisiones(){")
end = html.index("\n\nfunction renderReabast", start)
html = html[:start] + new_rdecisiones + html[end:]

path.write_text(html, encoding="utf-8")
print("patched", path)
