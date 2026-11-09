/* Qui vote quoi ? — lit les fichiers JSON produits chaque jour par le pipeline (dossier data/). */
(function () {
  "use strict";
  var REPO = "https://github.com/qui-vote-quoi-app/qui-vote-quoi";
  var AN = "https://www.assemblee-nationale.fr";
  var INSPIRATION = "https://www.instagram.com/votes_assemblee_nationale/";
  var K = 4.22, CX = 118.3 * K, CY = 132 * K, R = 8;
  var LABEL = { pour: "Pour", contre: "Contre", abst: "Abstention", nv: "Non-votant" };
  var MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  var EXT = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M9 3h4v4M13 3L7 9M12 10v3H3V4h3"/></svg>';

  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var get = function (p) { return fetch("data/" + p).then(function (r) { if (!r.ok) throw new Error(p); return r.json(); }); };
  var majuscule = function (t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : ""; };
  var dateFr = function (d) { var p = d.split("-"); return (+p[2]) + " " + MOIS[+p[1] - 1] + " " + p[0]; };
  var ord = function (n) { return n === 1 ? "1re" : n + "e"; };

  var st = { meta: null, groupes: {}, deps: [], places: {}, mois: {}, moisCharges: 0, lv: 1, q: "", num: null,
    s: null, mode: "vote", grp: null, sel: null, seatInfo: {} };

  /* ---------------- Hémicycle ---------------- */
  var svg = $("svg"), NS = "http://www.w3.org/2000/svg", circles = {};
  function dessinerSieges() {
    var g = document.createElementNS(NS, "g");
    Object.keys(st.places).forEach(function (num) {
      var p = st.places[num], c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", (p[0] * K).toFixed(1)); c.setAttribute("cy", (p[1] * K).toFixed(1)); c.setAttribute("r", R);
      c.setAttribute("class", "seat vide"); c.dataset.place = num; g.appendChild(c); circles[num] = c;
    });
    svg.appendChild(g);
    [["cbig", CY - 112, "center-big"], ["csub", CY - 72, "center-sub"]].forEach(function (t) {
      var e = document.createElementNS(NS, "text"); e.id = t[0]; e.setAttribute("x", CX); e.setAttribute("y", t[1]);
      e.setAttribute("text-anchor", "middle"); e.setAttribute("class", t[2]); svg.appendChild(e);
    });
  }
  function peindre() {
    Object.keys(circles).forEach(function (num) {
      var c = circles[num], info = st.seatInfo[num], cls = "seat";
      if (!info) { c.setAttribute("class", "seat vide" + (st.grp ? " dim" : "")); c.style.fill = ""; return; }
      if (st.mode === "vote") { cls += " " + info.pos; c.style.fill = ""; }
      else { c.style.fill = (st.groupes[info.po] || {}).couleur || "#888"; }
      if (st.grp && info.po !== st.grp) cls += " dim";
      if (st.sel === info.dep) cls += " sel";
      c.setAttribute("class", cls);
    });
  }

  /* ---------------- Index des scrutins ---------------- */
  function chargerMoisSuivant() {
    var m = st.meta.mois[st.moisCharges];
    if (!m) return Promise.resolve();
    st.moisCharges++;
    return get("mois/" + m + ".json").then(function (l) { st.mois[m] = l; rendreListe(); });
  }
  function rendreListe() {
    var q = st.q.trim().toLowerCase(), html = "", dernierJour = "", n = 0;
    st.meta.mois.slice(0, st.moisCharges).forEach(function (m) {
      (st.mois[m] || []).forEach(function (s) {
        if (s.niv > st.lv) return;
        if (q && (s.titre + " " + s.num).toLowerCase().indexOf(q) < 0) return;
        n++;
        if (s.date !== dernierJour) { html += '<div class="day">' + dateFr(s.date) + "</div>"; dernierJour = s.date; }
        var ok = s.sort === "adopté";
        html += '<button class="sitem" data-num="' + s.num + '" aria-current="' + (s.num === st.num) + '">' +
          '<span class="res" style="background:var(' + (ok ? "--pour" : "--contre") + ')" title="' + (ok ? "Adopté" : "Rejeté") + '">' + (ok ? "A" : "R") + "</span>" +
          '<span style="min-width:0"><span class="t">' + esc(majuscule(s.titre)) + '</span><span class="m"><span class="cat c-' + s.cat + '">' + libelleCat(s.cat) + '</span><span class="num">n° ' + s.num + "</span>" +
          (s.syn === "publiee" ? "<span>· synthèse du débat</span>" : "") + "</span></span></button>";
      });
    });
    if (!n) html = '<p class="sempty">' + (q ? "Aucun scrutin ne correspond à cette recherche dans les mois chargés." : "Aucun scrutin de ce niveau sur la période chargée.") + "</p>";
    if (st.moisCharges < st.meta.mois.length) html += '<button class="more" id="more">Charger le mois précédent</button>';
    $("slist").innerHTML = html;
    var more = $("more"); if (more) more.onclick = chargerMoisSuivant;
  }
  function libelleCat(c) {
    return { ensemble: "Vote sur l'ensemble", motion: "Motion de procédure", censure: "Motion de censure", declaration: "Déclaration du Gouvernement",
      article: "Article", amendement: "Amendement", procedure: "Procédure" }[c] || "Autre";
  }

  /* ---------------- Scrutin ---------------- */
  function ouvrir(num) {
    st.num = num; st.sel = null; st.grp = null;
    return get("scrutins/" + num + ".json").then(function (s) {
      st.s = s; st.seatInfo = {};
      s.groupes.forEach(function (g) {
        Object.keys(g.votes).forEach(function (pos) {
          var v = g.votes[pos];
          for (var i = 0; i < v.length; i += 2) st.seatInfo[String(v[i + 1])] = { dep: v[i], pos: pos, po: g.po };
        });
      });
      rendreTout();
      document.title = "Scrutin n° " + num + " · Qui vote quoi ?";
    }).catch(function () {
      $("summary").innerHTML = '<p class="empty-deb">Ce scrutin est introuvable.</p>';
    });
  }
  function compte(filtre) {
    var c = { pour: 0, contre: 0, abst: 0, nv: 0 };
    st.s.groupes.forEach(function (g) { if (!filtre || filtre(g)) ["pour", "contre", "abst", "nv"].forEach(function (k) { c[k] += g.decompte[k]; }); });
    return c;
  }
  function barre(c) {
    var t = c.pour + c.contre + c.abst + c.nv || 1;
    return '<div class="bar" aria-hidden="true"><span style="width:' + c.pour / t * 100 + '%;background:var(--pour)"></span><span style="width:' + c.contre / t * 100 + '%;background:var(--contre)"></span><span style="width:' + c.abst / t * 100 + '%;background:var(--abst)"></span></div>';
  }
  function rendreSynthese() {
    var s = st.s, ok = s.sort === "adopté", focus = "";
    if (st.grp) {
      var g = s.groupes.filter(function (x) { return x.po === st.grp; })[0], gi = st.groupes[st.grp] || {};
      var d = g.decompte, pos = g.position;
      focus = '<div class="focusline"><i class="sq" style="background:' + esc(gi.couleur) + '"></i><b>' + esc(gi.libelle || st.grp) + "</b> : position majoritaire <b>" + esc(pos || "—") +
        "</b> · " + d.pour + " pour, " + d.contre + " contre, " + d.abst + " abst., " + d.nv + " non-votants · " + g.membres + " membres</div>";
    }
    var liens = "";
    if (s.dossier) liens += '<a href="' + AN + "/dyn/17/dossiers/" + esc(s.dossier) + '" target="_blank" rel="noopener">' + EXT + "Texte discuté : " + esc(s.dossier_libelle || "dossier législatif") + "</a>";
    liens += '<a href="' + AN + "/dyn/17/scrutins/" + s.num + '" target="_blank" rel="noopener">' + EXT + "Scrutin sur le site de l'Assemblée</a>";
    liens += '<a href="' + REPO + "/issues/new?template=erreur.yml&title=" + encodeURIComponent("Scrutin n° " + s.num) + '" target="_blank" rel="noopener">' + EXT + "Signaler une erreur</a>";
    $("summary").innerHTML =
      '<div class="sum-head"><div style="min-width:0"><div class="meta"><span class="num">Scrutin n° ' + s.num + "</span><span>" + dateFr(s.date) + "</span><span>" + esc(majuscule(s.type_libelle)) + '</span><span class="cat c-' + s.categorie.cle + '">' + esc(s.categorie.libelle) + "</span></div><h2>" + esc(majuscule(s.titre)) + "</h2></div>" +
      '<span class="stamp ' + (ok ? "ok" : "ko") + '">' + esc(s.sort_libelle || (ok ? "Adopté" : "Rejeté")) + "</span></div>" +
      '<div class="links">' + liens + "</div>" +
      '<div class="counts"><div><b>' + s.votants + '</b><span class="k">votants</span></div><div><b>' + s.exprimes + '</b><span class="k">suffrages exprimés</span></div><div><b>' + s.requis + '</b><span class="k">majorité requise</span></div>' +
      '<div><b style="color:var(--pour)">' + s.pour + '</b><span class="k">pour</span></div><div><b style="color:var(--contre)">' + s.contre + '</b><span class="k">contre</span></div><div><b style="color:var(--abst)">' + s.abst + '</b><span class="k">abstentions</span></div></div>' +
      barre({ pour: s.pour, contre: s.contre, abst: s.abst, nv: s.nv }) + focus;
    $("cbig").textContent = ok ? "Adopté" : "Rejeté";
    $("cbig").style.fill = ok ? "var(--pour)" : "var(--contre)";
    $("csub").textContent = s.pour + " pour · " + s.contre + " contre · " + s.abst + " abst.";
  }
  function rendreGroupes() {
    var s = st.s;
    $("chips").innerHTML = '<button class="chip" data-po="" aria-pressed="' + !st.grp + '">Tous les groupes</button>' +
      s.groupes.map(function (g) { var gi = st.groupes[g.po] || {}; return '<button class="chip" data-po="' + g.po + '" aria-pressed="' + (st.grp === g.po) + '"><i class="sq" style="background:' + esc(gi.couleur) + '"></i>' + esc(gi.sigle || g.po) + "</button>"; }).join("");
    $("gtb").innerHTML = s.groupes.map(function (g) {
      var gi = st.groupes[g.po] || {}, d = g.decompte, pos = g.position, votants = d.pour + d.contre + d.abst;
      var cle = { pour: "pour", contre: "contre", abstention: "abst" }[pos];
      return '<tr tabindex="0" data-po="' + g.po + '" class="' + (st.grp === g.po ? "on" : "") + '"><td><span class="grp"><i class="sq" style="background:' + esc(gi.couleur) + ';margin:0"></i>' + esc(gi.libelle || g.po) + ' <span class="num" style="color:var(--muted)">' + esc(gi.sigle || "") + "</span></span></td>" +
        "<td>" + (cle && votants ? '<span class="pill ' + cle + '">' + LABEL[cle] + '</span> <span class="num note">' + d[cle] + "/" + g.membres + "</span>" : '<span class="note">—</span>') + "</td>" +
        '<td class="n">' + d.pour + '</td><td class="n">' + d.contre + '</td><td class="n">' + d.abst + '</td><td class="n">' + d.nv + "</td><td>" + barre(d) + "</td></tr>";
    }).join("");
  }
  function rendreDebat() {
    var s = st.s, syn = s.synthese, el = $("debate"), h = '<div class="debate-head"><h2>Le débat en bref</h2>' + (syn && syn.seance_jour ? '<span class="note">D\'après le compte rendu de la séance du ' + esc(syn.seance_jour) + "</span>" : "") + "</div>";
    var vide = function (t) { el.innerHTML = h + '<p class="empty-deb">' + t + "</p>"; };
    if (s.categorie.niveau !== 1) return vide("La synthèse des débats est réservée aux votes majeurs : votes sur l'ensemble d'un texte, motions et déclarations du Gouvernement. Les liens ci-dessus permettent de remonter au texte et à la séance.");
    if (s.synthese_statut === "retiree") return vide("La synthèse de ce vote a été retirée à la suite d'un signalement.");
    if (s.synthese_statut === "en_attente") return vide("Synthèse en attente : elle sera générée dès la publication du compte rendu de la séance, en général sous un à deux jours.");
    if (!syn) return vide("Pas de synthèse disponible pour ce vote. Le compte rendu intégral est accessible depuis la page du scrutin sur le site de l'Assemblée.");
    var objet = s.categorie.cle === "motion" || s.categorie.cle === "censure" ? "la motion" : "le texte";
    var arg = function (a) {
      var d = a.dep != null ? st.deps[a.dep] : null, gi = d ? st.groupes[d.groupe] || {} : {};
      return '<div class="arg"><p>' + esc(a.resume) + "</p><blockquote>« " + esc(a.citation) + " »</blockquote>" +
        '<div class="by">— ' + (d ? '<button data-dep="' + a.dep + '">' + esc(a.nom) + "</button>" + (gi.sigle ? " (" + esc(gi.sigle) + ")" : "") : esc(a.nom) + (a.qualite ? ", " + esc(a.qualite) : "")) + "</div></div>";
    };
    el.innerHTML = h +
      '<div class="ia"><b>Généré par IA</b><span>Cette synthèse est produite automatiquement par une intelligence artificielle à partir du compte rendu officiel, <strong>sans relecture humaine</strong>. Les citations sont vérifiées mot pour mot ; les résumés en gras ne sont attribués à personne. En cas d\'erreur, <a href="' + REPO + "/issues/new?template=erreur.yml&title=" + encodeURIComponent("Synthèse du scrutin n° " + s.num) + '" target="_blank" rel="noopener">signalez-la</a>.</span></div>' +
      '<p class="context">' + esc(syn.contexte) + "</p>" +
      '<div class="cols"><div class="col pour"><h3>Arguments pour ' + objet + "</h3>" + (syn.pour.length ? syn.pour.map(arg).join("") : '<p class="note">Aucun argument en ce sens dans le passage analysé.</p>') + "</div>" +
      '<div class="col contre"><h3>Arguments contre ' + objet + "</h3>" + (syn.contre.length ? syn.contre.map(arg).join("") : '<p class="note">Aucun argument en ce sens dans le passage analysé.</p>') + "</div></div>" +
      '<p class="note" style="margin:0">Modèle : ' + esc(syn.modele) + " · généré le " + esc((syn.genere_le || "").slice(0, 10)) + "</p>";
  }
  function rendreFiche() {
    var el = $("card");
    if (st.sel == null) {
      el.innerHTML = '<div class="eyebrow">Fiche député</div><p style="margin:0;color:var(--muted);font-size:14px">Cliquez sur un siège, sur un orateur du débat, ou recherchez un nom pour afficher sa fiche.</p>';
      return;
    }
    var d = st.deps[st.sel], info = null, place = null;
    Object.keys(st.seatInfo).forEach(function (p) { if (st.seatInfo[p].dep === st.sel) { info = st.seatInfo[p]; place = p; } });
    var gVote = info ? st.groupes[info.po] || {} : null, gAct = st.groupes[d.groupe] || {};
    var pos = info ? info.pos : null;
    var groupeVote = info ? st.s.groupes.filter(function (g) { return g.po === info.po; })[0] : null;
    var maj = groupeVote ? { pour: "pour", contre: "contre", abstention: "abst" }[groupeVote.position] : null;
    var alignement = !pos ? "Aucun vote enregistré pour ce député sur ce scrutin." : pos === "nv" ? "Non-votant sur ce scrutin." : (pos === maj ? "A voté comme la majorité de son groupe." : "A voté différemment de la majorité de son groupe.");
    el.innerHTML = '<button class="close" id="xclose" aria-label="Fermer la fiche">Fermer</button>' +
      '<div class="idt"><span class="av lg" style="background:' + esc(gAct.couleur || "#777") + '" aria-hidden="true">' + esc((d.prenom || "?")[0] + (d.nom || "?")[0]) + '</span><div style="min-width:0"><div class="eyebrow">Député' + (d.actif ? "" : " · mandat terminé") + "</div><h3>" + esc(d.prenom + " " + d.nom) + '</h3><span class="grp"><i class="sq" style="background:' + esc(gAct.couleur) + ';margin:0"></i>' + esc(gAct.libelle || "Sans groupe") + "</span></div></div>" +
      '<div><div class="eyebrow" style="margin-bottom:6px">Ce scrutin</div>' + (pos ? '<span class="pill ' + pos + '">' + LABEL[pos] + "</span>" : "") + '<div class="note" style="margin-top:4px">' + alignement + (gVote && info.po !== d.groupe ? " Groupe au moment du vote : " + esc(gVote.sigle) + "." : "") + "</div></div>" +
      "<dl><dt>Circonscription</dt><dd>" + esc(d.dept || "—") + (d.circo ? " (" + ord(d.circo) + ")" : "") + "</dd><dt>Place</dt><dd class=\"num\">n° " + esc(place || d.place || "—") + "</dd></dl>" +
      '<a class="btn" style="align-self:flex-start" href="' + AN + "/dyn/deputes/" + esc(d.id) + '" target="_blank" rel="noopener">Fiche officielle ' + EXT + "</a>";
    $("xclose").onclick = function () { choisir(null); };
  }
  function rendreTout() { peindre(); rendreSynthese(); rendreGroupes(); rendreDebat(); rendreFiche(); rendreListe(); }

  /* ---------------- Interactions ---------------- */
  var tip = $("tip"), hemi = $("hemi");
  function montrerTip(place) {
    var info = st.seatInfo[place]; if (!info) return;
    var d = st.deps[info.dep], g = st.groupes[info.po] || {};
    tip.innerHTML = '<span class="av" style="background:' + esc(g.couleur || "#777") + '" aria-hidden="true">' + esc((d.prenom || "?")[0] + (d.nom || "?")[0]) + '</span><div><div class="who">' + esc(d.prenom + " " + d.nom) + '</div><div class="sub"><i class="sq" style="background:' + esc(g.couleur) + '"></i>' + esc(g.sigle || "") + " · " + esc(d.dept || "") + '</div><span class="pill ' + info.pos + '" style="margin-top:3px">' + LABEL[info.pos] + "</span></div>";
    var r = circles[place].getBoundingClientRect(), h = hemi.getBoundingClientRect();
    var x = Math.max(130, Math.min(h.width - 130, r.left + r.width / 2 - h.left)), y = r.top - h.top;
    tip.style.left = x + "px"; tip.style.top = y + "px"; tip.style.transform = y < 70 ? "translate(-50%," + (r.height + 14) + "px)" : ""; tip.hidden = false;
  }
  svg.addEventListener("pointerover", function (e) { var p = e.target.dataset && e.target.dataset.place; if (p && e.pointerType !== "touch") montrerTip(p); });
  svg.addEventListener("pointerout", function (e) { if (e.target.dataset && e.target.dataset.place) tip.hidden = true; });
  svg.addEventListener("click", function (e) { var p = e.target.dataset && e.target.dataset.place; if (p && st.seatInfo[p]) choisir(st.seatInfo[p].dep); });
  function choisir(dep) {
    st.sel = dep; tip.hidden = true; peindre(); rendreFiche();
    if (dep != null && window.matchMedia("(max-width:1180px)").matches) $("card").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  $("debate").addEventListener("click", function (e) { var b = e.target.closest("button[data-dep]"); if (b) { choisir(+b.dataset.dep); hemi.scrollIntoView({ behavior: "smooth", block: "center" }); } });
  function filtrerGroupe(po) { st.grp = po || null; peindre(); rendreSynthese(); rendreGroupes(); }
  $("chips").addEventListener("click", function (e) { var b = e.target.closest(".chip"); if (b) filtrerGroupe(b.dataset.po); });
  $("gtb").addEventListener("click", function (e) { var r = e.target.closest("tr"); if (r) filtrerGroupe(st.grp === r.dataset.po ? null : r.dataset.po); });
  $("gtb").addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { var r = e.target.closest("tr"); if (r) { e.preventDefault(); filtrerGroupe(st.grp === r.dataset.po ? null : r.dataset.po); } } });
  function mode(m) { st.mode = m; $("m-vote").setAttribute("aria-pressed", m === "vote"); $("m-grp").setAttribute("aria-pressed", m === "grp"); peindre(); }
  $("m-vote").onclick = function () { mode("vote"); }; $("m-grp").onclick = function () { mode("grp"); };
  $("slist").addEventListener("click", function (e) { var b = e.target.closest(".sitem"); if (b) { location.hash = "s" + b.dataset.num; fermerMobile(); window.scrollTo({ top: 0, behavior: "smooth" }); } });
  $("sq").addEventListener("input", function () { st.q = this.value; rendreListe(); });
  [].forEach.call(document.querySelectorAll(".side-tools .seg button"), function (b) {
    b.onclick = function () { st.lv = +b.dataset.lv; [].forEach.call(b.parentNode.children, function (x) { x.setAttribute("aria-pressed", x === b); }); rendreListe(); };
  });
  var app = $("app"), mq = window.matchMedia("(max-width:900px)");
  $("toggle").onclick = function () {
    if (mq.matches) { fermerMobile(); return; }
    var c = app.classList.toggle("collapsed");
    this.setAttribute("aria-expanded", !c); this.setAttribute("aria-label", c ? "Déplier la liste des scrutins" : "Replier la liste des scrutins");
    try { localStorage.setItem("qvq-side", c ? "1" : "0"); } catch (e) {}
  };
  try { if (localStorage.getItem("qvq-side") === "1" && !mq.matches) app.classList.add("collapsed"); } catch (e) {}
  $("openside").onclick = function () { app.classList.add("mopen"); $("scrim").hidden = false; $("sq").focus(); };
  function fermerMobile() { app.classList.remove("mopen"); $("scrim").hidden = true; }
  $("scrim").onclick = fermerMobile;
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { if (app.classList.contains("mopen")) fermerMobile(); else if (st.sel != null) choisir(null); } });
  $("q").addEventListener("change", function () {
    var v = this.value.toLowerCase(), i = st.deps.findIndex(function (d) { return (d.prenom + " " + d.nom).toLowerCase() === v.replace(/\s*\(.*\)$/, ""); });
    if (i >= 0) { choisir(i); this.value = ""; }
  });
  window.addEventListener("hashchange", depuisHash);
  function depuisHash() {
    var m = /^#s(\d+)$/.exec(location.hash);
    var num = m ? +m[1] : premierMajeur();
    if (num && num !== st.num) ouvrir(num);
  }
  function premierMajeur() {
    var l = st.mois[st.meta.mois[0]] || [];
    var s = l.filter(function (x) { return x.niv === 1; })[0] || l[0];
    return s ? s.num : st.meta.dernier;
  }

  /* ---------------- Démarrage ---------------- */
  Promise.all([get("meta.json"), get("groupes.json"), get("deputes.json"), get("places.json")]).then(function (r) {
    st.meta = r[0]; st.groupes = r[1]; st.deps = r[2]; st.places = r[3].places;
    dessinerSieges();
    $("dl").innerHTML = st.deps.filter(function (d) { return d.actif; }).map(function (d) { return '<option value="' + esc(d.prenom + " " + d.nom) + '">'; }).join("");
    var src = (st.meta.sources || {}).scrutins;
    $("footer").innerHTML = "<span>Données : Assemblée nationale, data.assemblee-nationale.fr, Licence Ouverte 2.0" + (src ? " · mise à jour des données : " + esc(src) : "") + "</span>" +
      '<span>Site indépendant, sans lien avec l\'Assemblée nationale.</span>' +
      '<span>Projet très largement inspiré du travail du compte Instagram <a href="' + INSPIRATION + '" target="_blank" rel="noopener">@votes_assemblee_nationale</a>.</span>' +
      '<a href="' + REPO + '/blob/main/MENTIONS_LEGALES.md" target="_blank" rel="noopener">Mentions légales</a>' +
      '<a href="' + REPO + '/blob/main/docs/METHODOLOGIE.md" target="_blank" rel="noopener">Méthodologie</a>' +
      '<a href="' + REPO + '" target="_blank" rel="noopener">Code source</a>';
    return chargerMoisSuivant();
  }).then(depuisHash).catch(function (e) {
    $("summary").innerHTML = '<p class="empty-deb">Les données n\'ont pas pu être chargées. Réessayez dans quelques minutes.</p>';
    console.error(e);
  });
})();
