/* =====================================================================
   HK Pools — status engine (canonical)

   The ONE implementation of "is this pool open right now". It is injected
   verbatim into both index.html and hkpools-widget.js at build time, so the
   web app and the iOS widget can never disagree.

   Pure functions only: no DOM, no network, no Scriptable APIs. Takes a pool
   object from pools.json plus a Date, returns status. Node can run it as-is,
   which is how the parity tests work.
   ===================================================================== */

function hkNow(){
  return new Date(new Date().toLocaleString("en-US",{timeZone:"Asia/Hong_Kong"}));
}
function mins(t){ const p=t.split(":"); return (+p[0])*60 + (+p[1]); }
function fmt(t){
  let p=t.split(":"), h=+p[0], m=p[1], ap=h<12?"am":"pm";
  h=h%12||12; return h+":"+m+ap;
}
function isoDay(d){
  return d.getFullYear()+"-"+String(d.getMonth()+1).padStart(2,"0")
         +"-"+String(d.getDate()).padStart(2,"0");
}
function inMonthRange(rng, mo, day){
  if(!rng) return false;
  var m1=rng[0][0], d1=rng[0][1], m2=rng[1][0], d2=rng[1][1];
  var a=m1*100+d1, b=m2*100+d2, x=mo*100+day;
  return a<=b ? (x>=a && x<=b) : (x>=a || x<=b);
}

/* ---- one facility -------------------------------------------------- */
function facilityStatus(p, f, now){
  var mo=now.getMonth()+1, day=now.getDate(), wd=(now.getDay()+6)%7;
  var nowM=now.getHours()*60+now.getMinutes();
  var today=isoDay(now);
  var out={code:"shut", label:"Closed", note:f.note||"", reason:"", sessions:[]};

  if(!p.public || !f.public){
    out.code="priv"; out.label="Groups only";
    out.note=f.access_note||p.access_note||""; return out;
  }

  for(var i=0;i<p.maintenance.length;i++){
    var m=p.maintenance[i];
    if(inMonthRange(m.range,mo,day) &&
       (m.scope==="venue" || (m.targets && m.targets.indexOf(f.id)>=0))){
      out.label="Maintenance"; out.note=m.label; out.reason=m.label; return out;
    }
  }

  if(f.months && f.months.indexOf(mo)<0){ out.label="Out of season"; return out; }
  if(f.days && f.days.indexOf(wd)<0){ out.label="Not today"; return out; }

  var list, sdays;
  if(f.weekday_sessions && f.weekday_sessions.days.indexOf(wd)>=0){
    list=f.weekday_sessions.sessions; sdays=null;
  } else if(f.sessions){ list=f.sessions; sdays=f.session_days; }
  else { list=p.sessions; sdays=p.session_days; }
  if(!list || !list.length){ out.code="unk"; out.label="Unknown"; return out; }

  var sess=list.map(function(s,i){
    var d = sdays && sdays[String(i)];
    return {from:s[0], to:s[1], skipped: d ? d.indexOf(wd)<0 : false};
  });

  // Weekly cleansing is a venue-wide clock blackout, never a session index:
  // facilities that open from the 2nd session have a different session list.
  if(p.cleansing_weekday===wd){
    var w = p.cleansing_window ||
            (p.sessions && p.sessions.length>1 ? ["10:00", p.sessions[1][1]] : null);
    if(w){
      var split=[];
      sess.forEach(function(s){
        if(s.skipped){ split.push(s); return; }
        if(mins(s.to)<=mins(w[0]) || mins(s.from)>=mins(w[1])){ split.push(s); return; }
        if(mins(s.from)<mins(w[0])) split.push({from:s.from,to:w[0],skipped:false});
        if(mins(s.to)>mins(w[1]))   split.push({from:w[1],to:s.to,skipped:false});
      });
      sess=split; out.cleansing=true;
    }
  }

  var live=sess.filter(function(s){ return !s.skipped; });
  out.sessions=live;

  var closure=(p.closures||[]).filter(function(c){
    if(!c.targets || c.targets.indexOf(f.id)<0) return false;
    var s=c.start.slice(0,10), e=c.end?c.end.slice(0,10):"9999-12-31";
    if(!(s<=today && today<=e)) return false;
    var from = c.start.slice(0,10)===today ? mins(c.start.slice(11)) : 0;
    var to   = (c.end && c.end.slice(0,10)===today) ? mins(c.end.slice(11)) : 1440;
    return nowM>=from && nowM<to;
  })[0];
  if(closure){
    out.label="Closed";
    out.note=closure.reason + (closure.end ? "" : " (until further notice)");
    // `reason` marks a closure we can name; `note` may just be standing text
    // about the facility, which is never why it is shut right now.
    out.reason=out.note;
    return out;
  }

  var cur=live.filter(function(s){ return nowM>=mins(s.from) && nowM<mins(s.to); })[0];
  if(cur){ out.code="open"; out.label="Open"; out.until=cur.to; return out; }
  var next=live.filter(function(s){ return mins(s.from)>nowM; })[0];
  if(next){ out.code="soon"; out.label=fmt(next.from); out.nextRaw=next.from; return out; }
  return out;
}

/* ---- whole venue --------------------------------------------------- */
function venueStatus(p, now){
  var facs=p.facilities.map(function(f){ return {f:f, s:facilityStatus(p,f,now)}; });
  if(!p.public)
    return {code:"priv", label:"Groups only", facs:facs, openN:0, total:0, vague:[]};
  if(!facs.length)
    return {code:"unk", label:"Hours unknown", facs:facs, openN:0, total:0, vague:[]};

  var open=facs.filter(function(x){ return x.s.code==="open"; });
  var openN=open.length;
  var total=facs.filter(function(x){ return x.s.code!=="priv"; }).length;
  var lapOpen=open.some(function(x){ return x.f.lap; });

  // when open, the earliest closing time among open facilities
  var until=null;
  open.forEach(function(x){
    if(x.s.until && (!until || mins(x.s.until)<mins(until))) until=x.s.until;
  });
  // when shut, the earliest next opening
  var nextRaw=null;
  facs.forEach(function(x){
    if(x.s.nextRaw && (!nextRaw || mins(x.s.nextRaw)<mins(nextRaw))) nextRaw=x.s.nextRaw;
  });

  var today=isoDay(now);
  var vague=(p.closures||[]).filter(function(c){
    return !c.targets && c.start.slice(0,10)<=today &&
           (c.end?c.end.slice(0,10):"9999-12-31")>=today;
  });

  var cleansing=facs.some(function(x){ return x.s.cleansing; });

  var code, label;
  if(openN===0){ code="shut"; label = nextRaw ? "Opens "+fmt(nextRaw) : "Closed"; }
  else if(vague.length){ code="part"; label="Open · see notice"; }
  else if(openN===total){ code="open"; label="All open"; }
  else { code="part"; label=openN+" of "+total+" open"; }

  return {code:code, label:label, facs:facs, openN:openN, total:total,
          lapOpen:lapOpen, until:until, nextRaw:nextRaw, vague:vague,
          cleansing:cleansing};
}

/* Node/test export; harmless in a browser or Scriptable. */
if (typeof module !== "undefined" && module.exports)
  module.exports = {hkNow, mins, fmt, isoDay, inMonthRange, facilityStatus, venueStatus};
