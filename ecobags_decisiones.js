function cobInfo(vMes, stk){
  if(vMes>0){
    var c=stk/vMes;
    return{txt:c.toFixed(1)+'m',col:c<1?'#ef4444':c<2?'#f59e0b':c<3?'#3b82f6':'#10b981'};
  }
  if(stk>0)return{txt:'—',col:'#7a7b95'};
  return{txt:'0m',col:'#ef4444'};
}
function needBadge(vMes,stk,need){
  if(vMes<=0&&stk<=0)return'<span style="background:rgba(122,123,149,.12);color:#7a7b95;border-radius:5px;padding:2px 8px;font-size:.66rem">Sin movimiento</span>';
  if(vMes<=0&&stk>0)return'<span style="background:rgba(59,130,246,.12);color:#3b82f6;border-radius:5px;padding:2px 8px;font-size:.66rem">Stock sin ventas</span>';
  if(need>0)return'<span style="background:rgba(245,158,11,.18);color:#f59e0b;border-radius:5px;padding:2px 8px;font-size:.66rem;font-weight:700">Comprar +'+need+'</span>';
  return'<span style="background:rgba(16,185,129,.12);color:#10b981;border-radius:5px;padding:2px 8px;font-size:.66rem">✓ OK</span>';
}
function rowNeedBadge(vMes,stk,need){
  if(vMes<=0&&stk<=0)return'<span style="margin-left:auto;font-size:.63rem;color:#7a7b95">Sin movimiento</span>';
  if(vMes<=0&&stk>0)return'<span style="margin-left:auto;font-size:.63rem;color:#3b82f6">Stock sin ventas</span>';
  if(need>0)return'<span style="margin-left:auto;background:rgba(245,158,11,.15);color:#f59e0b;border-radius:4px;padding:1px 7px;font-size:.63rem;font-weight:700">+'+need+' compra</span>';
  return'<span style="margin-left:auto;font-size:.63rem;color:#10b981">✓ OK</span>';
}

function rDecisiones(){
  var meses=_decMeses||2;
  var TORD={'XS':0,'S':1,'M':2,'L':3,'XL':4,'2XL':5,'3XL':6,'2':0,'4':1,'6':2,'8':3,'10':4,'12':5,'14':6};

  var prodGrid=document.getElementById('propGrid');
  if(prodGrid){
    var modelList=['ECO BAG'];
    prodGrid.innerHTML='';
    modelList.forEach(function(mod){
      var smry=DATA.summary_prod[mod];
      if(!smry)return;
      var rows=DATA.prod_curve.filter(function(r){
        return r.modelo===mod&&r.color.indexOf('/')>=0;
      });
      var smryCob=cobInfo(smry.v_mes,smry.stk_total);

      var byColor={};
      rows.forEach(function(r){
        if(!byColor[r.color])byColor[r.color]={rows:[],totalStk:0,totalNeed1:0,totalNeed2:0,totalNeed3:0,v_mes:0};
        byColor[r.color].rows.push(r);
        byColor[r.color].totalStk+=r.stk_total;
        byColor[r.color].totalNeed1+=r.need_1m;
        byColor[r.color].totalNeed2+=r.need_2m;
        byColor[r.color].totalNeed3+=r.need_3m;
        byColor[r.color].v_mes+=r.v_mes;
      });
      var colorKeys=Object.keys(byColor).sort(function(a,b){return byColor[b].v_mes-byColor[a].v_mes;});

      var colorsHtml=colorKeys.map(function(col){
        var cdata=byColor[col];
        var need=meses===1?cdata.totalNeed1:meses===2?cdata.totalNeed2:cdata.totalNeed3;
        var colCob=cobInfo(cdata.v_mes,cdata.totalStk);
        var sortedRows=cdata.rows.slice().sort(function(a,b){return(TORD[a.talla]||99)-(TORD[b.talla]||99);});
        var showTallas=sortedRows.length>1||sortedRows[0].talla!=='UNI';
        var tallasHtml=showTallas?sortedRows.map(function(r){
          var tn=meses===1?r.need_1m:meses===2?r.need_2m:r.need_3m;
          var rc=cobInfo(r.v_mes,r.stk_total);
          return '<div style="display:flex;align-items:center;gap:6px;padding:3px 8px 3px 12px;background:rgba(0,0,0,.15);border-radius:5px;margin-bottom:2px">'
            +'<span style="font-family:var(--fm);font-size:.68rem;color:var(--mu);width:28px">'+r.talla+'</span>'
            +'<span style="font-family:var(--fm);font-size:.65rem;color:var(--mu2)">'+r.v_mes.toFixed(1)+'/mes</span>'
            +'<span style="font-family:var(--fm);font-size:.65rem;color:var(--mu2)">stk '+r.stk_total+'</span>'
            +'<span style="font-family:var(--fm);font-size:.65rem;color:'+rc.col+';font-weight:700">'+rc.txt+'</span>'
            +rowNeedBadge(r.v_mes,r.stk_total,tn)
            +'</div>';
        }).join(''):'';
        return '<div style="background:rgba(0,0,0,.2);border-radius:8px;padding:8px 10px;margin-bottom:6px">'
          +'<div style="display:flex;align-items:center;gap:8px;margin-bottom:'+(showTallas?'6':'0')+'px">'
          +'<span class="chip" style="background:'+cn(col)+'"></span>'
          +'<span style="font-size:.73rem;font-weight:700">'+dLbl(col,col)+'</span>'
          +'<span style="font-family:var(--fm);font-size:.64rem;color:var(--mu2)">'+cdata.v_mes.toFixed(1)+'/mes · stk '+cdata.totalStk+'</span>'
          +'<span style="font-family:var(--fm);font-size:.64rem;color:'+colCob.col+';font-weight:700;margin-left:auto">'+colCob.txt+' cob</span>'
          +needBadge(cdata.v_mes,cdata.totalStk,need)
          +'</div>'+tallasHtml+'</div>';
      }).join('');

      var card=document.createElement('div');
      card.className='card';
      card.innerHTML='<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">'
        +'<h3 style="margin:0">'+mod+'</h3>'
        +'<span style="font-family:var(--fm);font-size:.72rem;color:var(--mu2)">'+smry.v_mes.toFixed(0)+'/mes · stk '+smry.stk_total+'</span>'
        +'<span style="margin-left:auto;font-family:var(--fm);font-size:.78rem;font-weight:800;color:'+smryCob.col+'">'+smryCob.txt+' meses cobertura</span>'
        +'</div>'
        +'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:12px">'
        +'<div style="text-align:center;background:rgba(99,102,241,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#818cf8">'+smry.need_1m+'</div><div style="font-size:.63rem;color:var(--mu)">Comprar 1 mes</div></div>'
        +'<div style="text-align:center;background:rgba(245,158,11,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#f59e0b">'+smry.need_2m+'</div><div style="font-size:.63rem;color:var(--mu)">Comprar 2 meses</div></div>'
        +'<div style="text-align:center;background:rgba(244,63,94,.1);border-radius:8px;padding:8px"><div style="font-family:var(--fm);font-size:1.1rem;font-weight:800;color:#f43f5e">'+smry.need_3m+'</div><div style="font-size:.63rem;color:var(--mu)">Comprar 3 meses</div></div>'
        +'</div>'
        +'<div style="font-size:.67rem;color:var(--mu2);margin-bottom:8px">📦 Stock taller: '+smry.stk_pt+' und &nbsp;·&nbsp; Velocidad: últimos meses cerrados</div>'
        +'<div>'+colorsHtml+'</div>';
      prodGrid.appendChild(card);
    });
  }

  var reabastGrid=document.getElementById('reabastGrid');
  if(reabastGrid){
    var mesesActivos=getMesesActivos();
    var nMeses=Math.min(meses,mesesActivos.length)||1;
    var EXCLUIR_RESTOCK=[];
    var tiendaData={};
    DATA.raw_rows.forEach(function(r){
      if(EXCLUIR_RESTOCK.indexOf(r.tienda)>=0)return;
      if(mesesActivos.slice(-nMeses).indexOf(r.mes)<0)return;
      if(!tiendaData[r.tienda])tiendaData[r.tienda]={v:0,items:{},proyectada:false,nota:''};
      tiendaData[r.tienda].v+=r.v;
      tiendaData[r.tienda].items[r.color]=(tiendaData[r.tienda].items[r.color]||0)+r.v;
    });

    var marNeed=meses===1?DATA.margarita.need_1m:meses===2?DATA.margarita.need_2m:DATA.margarita.need_3m;
    if(marNeed>0)tiendaData['MARGARITA 🆕']={v:marNeed,items:{},proyectada:true,nota:DATA.margarita.nota};
    if(marNeed>0){DATA.margarita.skus.forEach(function(s){
      var need=meses===1?s.need_1m:meses===2?s.need_2m:s.need_3m;
      if(need>0)tiendaData['MARGARITA 🆕'].items[s.COLOR]=(tiendaData['MARGARITA 🆕'].items[s.COLOR]||0)+need;
    });tiendaData['MARGARITA 🆕'].nota=DATA.margarita.nota;}

    if(tiendaData['TOLON'])tiendaData['TOLON'].nota='';

    var tiendas=Object.keys(tiendaData).sort(function(a,b){return tiendaData[b].v-tiendaData[a].v;});

    reabastGrid.innerHTML='<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px">'
      +tiendas.map(function(t){
        var td=tiendaData[t];
        var itemKeys=Object.keys(td.items).sort(function(a,b){return(td.items[b]||0)-(td.items[a]||0);});
        var topItems=itemKeys.slice(0,8);
        var isNew=td.proyectada;
        return '<div style="background:var(--s2);border-radius:10px;padding:12px;border:1px solid '+(isNew?'rgba(249,115,22,.3)':'var(--brd)')+';">'
          +'<div style="display:flex;align-items:center;gap:6px;margin-bottom:6px">'
          +'<span style="font-weight:700;font-size:.8rem">🏪 '+t+'</span>'
          +(isNew?'<span style="background:rgba(249,115,22,.15);color:#f97316;border-radius:4px;padding:1px 6px;font-size:.61rem">Proyectada</span>':'')
          +'</div>'
          +(td.nota?'<div style="font-size:.62rem;color:var(--mu2);margin-bottom:6px;font-style:italic">'+td.nota+'</div>':'')
          +'<div style="font-family:var(--fm);font-size:.68rem;color:var(--mu);margin-bottom:8px">'+td.v+' und sugeridas / '+nMeses+' mes(es)</div>'
          +topItems.map(function(k){
            return '<div style="display:flex;justify-content:space-between;align-items:center;font-size:.69rem;padding:3px 0;border-bottom:1px solid var(--brd)">'
              +'<span style="color:var(--tx)">'+dLbl(k,k)+'</span>'
              +'<span style="color:var(--a2);font-family:var(--fm);font-weight:700">'+td.items[k]+'</span></div>';
          }).join('')
          +(itemKeys.length>8?'<div style="font-size:.61rem;color:var(--mu2);margin-top:5px">+ '+(itemKeys.length-8)+' diseños más</div>':'')
          +'</div>';
      }).join('')
      +'</div>';
  }
}
