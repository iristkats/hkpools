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

/* ---- one day, one facility ----------------------------------------- */

/* The sessions a facility runs on a given date, before any clock is applied.
   Split out of facilityStatus so the same rules — maintenance, season,
   weekday, cleansing — can be asked about tomorrow, which is how the
   overnight "opens 6:30am" is worked out. */
function daySessions(p, f, d){
  var mo=d.getMonth()+1, day=d.getDate(), wd=(d.getDay()+6)%7;

  for(var i=0;i<p.maintenance.length;i++){
    var m=p.maintenance[i];
    if(inMonthRange(m.range,mo,day) &&
       (m.scope==="venue" || (m.targets && m.targets.indexOf(f.id)>=0)))
      return {blocked:"Maintenance", note:m.label, live:[]};
  }
  if(f.months && f.months.indexOf(mo)<0) return {blocked:"Out of season", live:[]};
  if(f.days && f.days.indexOf(wd)<0) return {blocked:"Not today", live:[]};

  var list, sdays;
  if(f.weekday_sessions && f.weekday_sessions.days.indexOf(wd)>=0){
    list=f.weekday_sessions.sessions; sdays=null;
  } else if(f.sessions){ list=f.sessions; sdays=f.session_days; }
  else { list=p.sessions; sdays=p.session_days; }
  if(!list || !list.length) return {blocked:"Unknown", live:[]};

  var sess=list.map(function(s,i){
    var dd = sdays && sdays[String(i)];
    return {from:s[0], to:s[1], skipped: dd ? dd.indexOf(wd)<0 : false};
  });

  // Weekly cleansing is a venue-wide clock blackout, never a session index:
  // facilities that open from the 2nd session have a different session list.
  var cleansing=false;
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
      sess=split; cleansing=true;
    }
  }
  return {blocked:null, cleansing:cleansing,
          live:sess.filter(function(s){ return !s.skipped; })};
}

/* The temporary closure covering this facility at this moment, if any. */
function closureAt(p, f, dayISO, minute){
  return (p.closures||[]).filter(function(c){
    if(!c.targets || c.targets.indexOf(f.id)<0) return false;
    var s=c.start.slice(0,10), e=c.end?c.end.slice(0,10):"9999-12-31";
    if(!(s<=dayISO && dayISO<=e)) return false;
    var from = s===dayISO ? mins(c.start.slice(11)) : 0;
    var to   = (c.end && c.end.slice(0,10)===dayISO) ? mins(c.end.slice(11)) : 1440;
    return minute>=from && minute<to;
  })[0];
}

/* When today has no session left, the first one on a later day. Looks a week
   ahead and no further: past that a venue is in annual maintenance, and a
   date months out is not the useful thing to say. */
function nextOpening(p, f, now){
  for(var n=1;n<=7;n++){
    var d=new Date(now.getFullYear(), now.getMonth(), now.getDate()+n);
    var day=daySessions(p,f,d);
    if(day.blocked || !day.live.length) continue;
    var iso=isoDay(d);
    for(var i=0;i<day.live.length;i++){
      if(!closureAt(p,f,iso,mins(day.live[i].from)))
        return {at:day.live[i].from, days:n, wd:(d.getDay()+6)%7};
    }
  }
  return null;
}

/* ---- one facility -------------------------------------------------- */
function facilityStatus(p, f, now){
  var nowM=now.getHours()*60+now.getMinutes();
  var today=isoDay(now);
  var out={code:"shut", label:"Closed", note:f.note||"", reason:"", sessions:[]};

  if(!p.public || !f.public){
    out.code="priv"; out.label="Groups only";
    out.note=f.access_note||p.access_note||""; return out;
  }

  var d=daySessions(p,f,now);
  if(d.blocked==="Maintenance"){
    out.label="Maintenance"; out.note=d.note; out.reason=d.note; return out;
  }
  if(d.blocked==="Out of season"){ out.label="Out of season"; return out; }
  if(d.blocked==="Not today"){
    out.label="Not today"; out.reopen=nextOpening(p,f,now); return out;
  }
  if(d.blocked==="Unknown"){ out.code="unk"; out.label="Unknown"; return out; }

  if(d.cleansing) out.cleansing=true;
  var live=d.live;
  out.sessions=live;

  var closure=closureAt(p,f,today,nowM);
  if(closure){
    out.label="Closed";
    out.note=closure.reason + (closure.end ? "" : " (until further notice)");
    // `reason` marks a closure we can name; `note` may just be standing text
    // about the facility, which is never why it is shut right now.
    out.reason=out.note;
    return out;
  }

  var cur=live.filter(function(s){ return nowM>=mins(s.from) && nowM<mins(s.to); })[0];
  if(cur){
    out.code="open"; out.label="Open"; out.until=cur.to;
    // the session after this one, so the gap is visible before you set off
    live.forEach(function(s){
      if(mins(s.from)>=mins(cur.to) &&
         (!out.afterRaw || mins(s.from)<mins(out.afterRaw))) out.afterRaw=s.from;
    });
    return out;
  }
  var next=live.filter(function(s){ return mins(s.from)>nowM; })[0];
  if(next){ out.code="soon"; out.label=fmt(next.from); out.nextRaw=next.from; return out; }

  // nothing left today — say when it is back rather than just "closed"
  out.reopen=nextOpening(p,f,now);
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
  // when open, when swimming resumes after that earliest close
  var resumeRaw=null;
  open.forEach(function(x){
    if(x.s.afterRaw && (!resumeRaw || mins(x.s.afterRaw)<mins(resumeRaw)))
      resumeRaw=x.s.afterRaw;
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

  // shut for the rest of today: the soonest any facility is back
  var reopen=null;
  if(openN===0 && !nextRaw)
    facs.forEach(function(x){
      var r=x.s.reopen;
      if(!r) return;
      if(!reopen || r.days<reopen.days ||
         (r.days===reopen.days && mins(r.at)<mins(reopen.at))) reopen=r;
    });

  var code, label;
  if(openN===0){
    code="shut";
    label = nextRaw ? "Opens "+fmt(nextRaw)
          : reopen ? "Opens "+fmt(reopen.at) : "Closed";
  }
  else if(vague.length){ code="part"; label="Open · see notice"; }
  else if(openN===total){ code="open"; label="All open"; }
  else { code="part"; label=openN+" of "+total+" open"; }

  return {code:code, label:label, facs:facs, openN:openN, total:total,
          lapOpen:lapOpen, until:until, resumeRaw:resumeRaw, nextRaw:nextRaw,
          reopen:reopen, vague:vague, cleansing:cleansing};
}

/* Node/test export; harmless in a browser or Scriptable. */
if (typeof module !== "undefined" && module.exports)
  module.exports = {hkNow, mins, fmt, isoDay, inMonthRange, daySessions,
                  closureAt, nextOpening, facilityStatus, venueStatus};
