/* Qui vote quoi ? — lit les fichiers JSON produits chaque jour par le pipeline (dossier data/).
   Trois vues : scrutins (#s9759), députés (#d-PA794562), groupes (#g-PO845401). */
(function () {
  "use strict";
  var REPO = "https://github.com/qui-vote-quoi-app/qui-vote-quoi";
  var AN = "https://www.assemblee-nationale.fr";
  var INSPIRATION = "https://www.instagram.com/votes_assemblee_nationale/";
  var K = 4.22, CX = 118.3 * K, CY = 132 * K, R = 8;
  var LABEL = { pour: "Pour", contre: "Contre", abst: "Abstention", nv: "Non-votant.e" };
  var POS = ["pour", "contre", "abst", "nv"];
  var MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"];
  var CAT_LIB = { ensemble: "Vote sur l'ensemble", motion: "Motion de procédure", censure: "Motion de censure", declaration: "Déclaration du Gouvernement",
    article: "Article", amendement: "Amendement", procedure: "Procédure", autre: "Autre" };
  var NIVEAUX = [[1, "Majeurs"], [2, "+ articles"], [3, "Tous"]];
  var EXT = '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><path d="M9 3h4v4M13 3L7 9M12 10v3H3V4h3"/></svg>';
  var PAGE = 150;
  var PAGES = [["alertes", "Recevoir les alertes"], ["a-propos", "À propos"], ["methodologie", "Méthodologie"], ["faq", "Questions fréquentes"],
    ["donnees-personnelles", "Données personnelles"], ["mentions-legales", "Mentions légales"], ["contact", "Contact"]];

  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  /* meta.json est toujours revérifié ; les autres fichiers portent la date de mise à jour (jamais de version périmée). */
  var VERSION = "";
  var get = function (p) {
    var url = "data/" + p + (VERSION ? "?v=" + encodeURIComponent(VERSION) : "");
    return fetch(url, p === "meta.json" ? { cache: "no-cache" } : undefined).then(function (r) { if (!r.ok) throw new Error(p); return r.json(); });
  };
  var cache = {};
  var getCache = function (p) { return cache[p] || (cache[p] = get(p)); };
  var majuscule = function (t) { return t ? t.charAt(0).toUpperCase() + t.slice(1) : ""; };
  var dateFr = function (d) { var p = d.split("-"); return (+p[2]) + " " + MOIS[+p[1] - 1] + " " + p[0]; };
  var dateCourte = function (d) { var p = d.split("-"); return p[2] + "/" + p[1] + "/" + p[0]; };
  var ord = function (n) { return n === 1 ? "1re" : n + "e"; };
  var norm = function (t) { return (t || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, ""); };
  var genre = function (d) { return d.civ === "Mme" ? "Députée" : "Député"; };
  var initiales = function (d) { return (d.prenom || "?")[0] + (d.nom || "?")[0]; };
  /* Vignette d'un député : photo officielle si disponible, sinon initiales ; liseré à la couleur du groupe. */
  var avatar = function (d, cls, couleur) {
    var c = esc(couleur || "#777");
    if (d.photo) return '<span class="av ph' + (cls ? " " + cls : "") + '" style="border-color:' + c + '" aria-hidden="true"><img src="data/photos/' + esc(d.id) + '.webp" alt="" loading="lazy" decoding="async"></span>';
    return '<span class="av' + (cls ? " " + cls : "") + '" style="background:' + c + '" aria-hidden="true">' + esc(initiales(d)) + "</span>";
  };

  var st = {
    vue: null, meta: null, idx: null, parNum: {}, groupes: {}, deps: [], depParId: {}, places: {},
    // barre latérale
    f: { lv: 1, q: "", theme: "" }, limite: PAGE, dq: "", dgrp: "", danciens: false,
    // scrutin affiché
    num: null, s: null, grp: null, sel: null, seatInfo: {},
    // historique affiché
    h: null
  };

  /* ================= Hémicycle ================= */
  var svg = $("svg"), NS = "http://www.w3.org/2000/svg", circles = {}, hemi = $("hemi"), tip = $("tip");
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
  function centrerHemicycle() { requestAnimationFrame(function () { hemi.scrollLeft = (hemi.scrollWidth - hemi.clientWidth) / 2; }); }
  function peindre() {
    Object.keys(circles).forEach(function (num) {
      var c = circles[num], info = st.seatInfo[num];
      if (!info) { c.setAttribute("class", "seat vide" + (st.grp ? " dim" : "")); return; }
      var cls = "seat " + info.pos;
      if (st.grp && info.po !== st.grp) cls += " dim";
      if (st.sel === info.dep) cls += " sel";
      c.setAttribute("class", cls);
    });
  }

  /* ================= Barre latérale ================= */
  function selectThemes(id, val) {
    return '<label class="sr" for="' + id + '">Thème</label><select id="' + id + '"><option value="">Tous les thèmes</option>' +
      st.idx.themes.map(function (t, i) { return '<option value="' + i + '"' + (String(val) === String(i) ? " selected" : "") + ">" + esc(t) + "</option>"; }).join("") +
      '<option value="-1"' + (String(val) === "-1" ? " selected" : "") + ">Sans commission identifiée</option></select>";
  }
  function segNiveaux(id, val) {
    return '<div class="seg" role="group" aria-label="Niveau de détail" id="' + id + '">' +
      NIVEAUX.map(function (n) { return '<button type="button" data-lv="' + n[0] + '" aria-pressed="' + (val === n[0]) + '">' + n[1] + "</button>"; }).join("") + "</div>";
  }
  function outilsLateraux() {
    var el = $("side-tools");
    if (st.vue === "infos") { el.innerHTML = ""; }
    else if (modeLateral() === "scrutins") {
      el.innerHTML = '<label for="sq" class="sr">Rechercher un scrutin</label><input id="sq" type="search" placeholder="Rechercher un texte, un n°…" autocomplete="off" value="' + esc(st.f.q) + '">' +
        segNiveaux("slv", st.f.lv) + selectThemes("sth", st.f.theme);
      $("sq").oninput = function () { st.f.q = this.value; st.limite = PAGE; listeLaterale(); };
      $("slv").onclick = function (e) { var b = e.target.closest("button"); if (!b) return; st.f.lv = +b.dataset.lv; st.limite = PAGE; outilsLateraux(); listeLaterale(); };
      $("sth").onchange = function () { st.f.theme = this.value; st.limite = PAGE; listeLaterale(); };
    } else if (st.vue === "deputes") {
      var gps = Object.keys(st.groupes).filter(function (po) { return !st.groupes[po].fin; }).sort(function (a, b) { return st.groupes[a].ordre - st.groupes[b].ordre; });
      el.innerHTML = '<label for="dq" class="sr">Rechercher un.e député.e</label><input id="dq" type="search" placeholder="Nom, département ou commune…" autocomplete="off" value="' + esc(st.dq) + '">' +
        '<label class="sr" for="dgrp">Groupe</label><select id="dgrp"><option value="">Tous les groupes</option>' +
        gps.map(function (po) { return '<option value="' + po + '"' + (st.dgrp === po ? " selected" : "") + ">" + esc(st.groupes[po].sigle + " · " + st.groupes[po].libelle) + "</option>"; }).join("") + "</select>" +
        '<label class="chk"><input type="checkbox" id="danc"' + (st.danciens ? " checked" : "") + "> Inclure les ancien.ne.s député.e.s</label>";
      $("dq").oninput = function () { st.dq = this.value; listeLaterale(); };
      $("dgrp").onchange = function () { st.dgrp = this.value; listeLaterale(); };
      $("danc").onchange = function () { st.danciens = this.checked; listeLaterale(); };
    } else {
      el.innerHTML = "";
    }
    el.hidden = !el.innerHTML;
  }
  function listeLaterale() {
    var el = $("slist"), html = "";
    if (st.vue === "infos") {
      el.innerHTML = PAGES.map(function (p) {
        return '<a class="pitem" href="#' + p[0] + '"' + (st.page === p[0] ? ' aria-current="page"' : "") + ">" + p[1] + "</a>";
      }).join("");
      return;
    }
    if (modeLateral() === "scrutins") {
      var q = norm(st.f.q.trim()), n = 0, jour = "", total = 0;
      st.idx.s.forEach(function (r) {
        if (r[3] > st.f.lv) return;
        if (st.f.theme !== "" && String(r[5]) !== st.f.theme) return;
        if (q && norm(r[7] + " " + r[0]).indexOf(q) < 0) return;
        total++;
        if (n >= st.limite) return;
        n++;
        if (r[1] !== jour) { html += '<div class="day">' + dateFr(r[1]) + "</div>"; jour = r[1]; }
        var cat = st.idx.cats[r[2]];
        html += '<a class="sitem" href="#s' + r[0] + '" aria-current="' + (r[0] === st.num) + '">' + resultat(r[4]) +
          '<span style="min-width:0"><span class="t">' + esc(majuscule(r[7])) + '</span><span class="m"><span class="cat c-' + cat + '">' + CAT_LIB[cat] + '</span><span class="num">n° ' + r[0] + "</span>" +
          (r[5] >= 0 ? "<span>" + esc(st.idx.themes[r[5]]) + "</span>" : "") + (r[6] === "publiee" ? "<span>· débat résumé</span>" : "") + "</span></span></a>";
      });
      if (!total) html = '<p class="sempty">Aucun scrutin ne correspond à ces critères.</p>';
      else if (total > n) html += '<button class="more" id="more" type="button">Afficher plus (' + (total - n) + " restants)</button>";
    } else if (st.vue === "deputes") {
      var viaCommune = {}, coms = [];
      if (cleDep(st.dq).length >= 2) {
        if (!cache.communesListe) chargerCommunes().then(function (c) { cache.communesListe = c; if (st.vue === "deputes" && st.dq) listeLaterale(); });
        var nq = cleDep(st.dq), cp = /^\d{5}$/.test(st.dq.trim()) ? st.dq.trim() : null;
        (cache.communesListe || []).forEach(function (c) { if (cp ? c[3].indexOf(cp) >= 0 : cleDep(c[0]) === nq) { coms.push(c); c[2].forEach(function (n) { viaCommune[cleDep(c[1]) + "|" + n] = 1; }); } });
      }
      var dq = norm(st.dq.trim()), liste = st.deps.map(function (d, i) { return [d, i]; }).filter(function (x) {
        var d = x[0];
        if (!st.danciens && !d.actif) return false;
        if (st.dgrp && d.groupe !== st.dgrp) return false;
        return !dq || norm(d.prenom + " " + d.nom + " " + (d.dept || "")).indexOf(dq) >= 0 || viaCommune[cleDep(d.dept || "") + "|" + d.circo];
      }).sort(function (a, b) { return a[0].nom.localeCompare(b[0].nom, "fr") || a[0].prenom.localeCompare(b[0].prenom, "fr"); });
      html = liste.map(function (x) {
        var d = x[0], g = st.groupes[d.groupe] || {};
        return '<a class="sitem ditem" href="#d-' + d.id + '" aria-current="' + (st.h && st.h.type === "d" && st.h.id === d.id) + '">' + avatar(d, "sm", g.couleur) + '<span style="min-width:0"><span class="t">' + esc(d.prenom + " " + d.nom) + '</span><span class="m"><span class="num">' + esc(g.sigle || "—") + "</span><span>" + esc(d.dept || "") + (d.circo ? " (" + ord(d.circo) + ")" : "") + "</span>" + (d.actif ? "" : "<span>· mandat terminé</span>") + "</span></span></a>";
      }).join("") || '<p class="sempty">Aucun.e député.e ne correspond.</p>';
      html = '<p class="sompte">' + liste.length + (liste.length > 1 ? " député.e.s" : " député.e") + "</p>" +
        (coms.length ? '<p class="note" style="margin:0 12px 8px">Commune' + (coms.length > 1 ? "s" : "") + " : " + esc(coms.slice(0, 3).map(function (c) { return c[0] + " (" + c[1] + ")"; }).join(", ")) + (coms.some(function (c) { return c[2].length > 1; }) ? ". Commune partagée entre plusieurs circonscriptions : cherchez votre adresse sur l'accueil pour trouver la vôtre." : "") + "</p>" : "") + html;
    } else {
      var effectifs = {};
      st.deps.forEach(function (d) { if (d.actif && d.groupe) effectifs[d.groupe] = (effectifs[d.groupe] || 0) + 1; });
      var pos = Object.keys(st.groupes).sort(function (a, b) { return (st.groupes[a].fin ? 1 : 0) - (st.groupes[b].fin ? 1 : 0) || st.groupes[a].ordre - st.groupes[b].ordre; });
      var anciens = false;
      html = pos.map(function (po) {
        var g = st.groupes[po], entete = "";
        if (g.fin && !anciens) { anciens = true; entete = '<div class="day">Anciens groupes</div>'; }
        return entete + '<a class="sitem gitem" href="#g-' + po + '" aria-current="' + (st.h && st.h.type === "g" && st.h.id === po) + '"><i class="sq lg" style="background:' + esc(g.couleur) + '"></i><span style="min-width:0"><span class="t">' + esc(g.libelle) + '</span><span class="m"><span class="num">' + esc(g.sigle) + "</span>" + (effectifs[po] ? "<span>" + effectifs[po] + " membres</span>" : "") + "</span></span></a>";
      }).join("");
    }
    el.innerHTML = html;
    var more = $("more"); if (more) more.onclick = function () { st.limite += PAGE; listeLaterale(); };
  }
  function resultat(adopte) {
    return '<span class="res" style="background:var(' + (adopte ? "--pour" : "--contre") + ')" title="' + (adopte ? "Adopté" : "Rejeté") + '">' + (adopte ? "A" : "R") + "</span>";
  }

  /* ================= Vue scrutin ================= */
  function ouvrirScrutin(num) {
    if (num === st.num && st.s) { rendreScrutin(); return; }
    st.num = num; st.sel = null; st.grp = null;
    var p = Math.floor(num / 100);
    getCache("scrutins/" + p + ".json").then(function (b) {
      var s = b[String(num)];
      if (!s) throw new Error("scrutin " + num);
      st.s = s; st.seatInfo = {};
      s.groupes.forEach(function (g) {
        Object.keys(g.votes).forEach(function (pos) {
          var v = g.votes[pos];
          for (var i = 0; i < v.length; i += 2) st.seatInfo[String(v[i + 1])] = { dep: v[i], pos: pos, po: g.po };
        });
      });
      rendreScrutin();
    }).catch(function () {
      $("summary").innerHTML = '<p class="empty-deb">Ce scrutin est introuvable.</p>';
    });
  }
  function rendreScrutin() {
    peindre(); rendreSynthese(); rendreGroupes(); rendreDebat(); rendreFiche(); listeLaterale();
    document.title = "Scrutin n° " + st.num + " · Qui vote quoi ?";
  }
  function barre(c) {
    var t = c.pour + c.contre + c.abst + c.nv || 1;
    return '<div class="bar" aria-hidden="true"><span style="width:' + c.pour / t * 100 + '%;background:var(--pour)"></span><span style="width:' + c.contre / t * 100 + '%;background:var(--contre)"></span><span style="width:' + c.abst / t * 100 + '%;background:var(--abst)"></span></div>';
  }
  function rendreSynthese() {
    var s = st.s, ok = s.sort === "adopté", focus = "";
    if (st.grp) {
      var g = s.groupes.filter(function (x) { return x.po === st.grp; })[0], gi = st.groupes[st.grp] || {}, d = g.decompte;
      focus = '<div class="focusline"><span><i class="sq" style="background:' + esc(gi.couleur) + '"></i><b>' + esc(gi.libelle || st.grp) + "</b> : position majoritaire <b>" + esc(g.position || "—") +
        "</b> · " + d.pour + " pour, " + d.contre + " contre, " + d.abst + " abst., " + d.nv + " non-votant.e.s · " + g.membres + ' membres</span><a href="#g-' + st.grp + '">Historique du groupe →</a></div>';
    }
    var liens = "";
    if (s.dossier) liens += '<a href="' + AN + "/dyn/17/dossiers/" + esc(s.dossier) + '" target="_blank" rel="noopener">' + EXT + "Texte discuté" + (s.dossier_libelle ? " : " + esc(s.dossier_libelle) : "") + "</a>";
    liens += '<a href="' + AN + "/dyn/17/scrutins/" + s.num + '" target="_blank" rel="noopener">' + EXT + "Scrutin sur le site de l'Assemblée</a>";
    liens += '<a href="' + REPO + "/issues/new?template=erreur.yml&title=" + encodeURIComponent("Scrutin n° " + s.num) + '" target="_blank" rel="noopener">' + EXT + "Signaler une erreur</a>";
    $("summary").innerHTML =
      '<div class="sum-head"><div style="min-width:0"><div class="meta"><span class="num">Scrutin n° ' + s.num + "</span><span>" + dateFr(s.date) + "</span><span>" + terme(s.type, esc(majuscule(s.type_libelle))) + '</span><span class="cat c-' + s.categorie.cle + '">' + terme(s.categorie.cle, esc(s.categorie.libelle)) + "</span>" + (s.theme ? '<span class="theme">' + esc(s.theme) + "</span>" : "") + "</div><h2>" + esc(majuscule(s.titre)) + "</h2>" + (s.resume && s.resume.resume ? '<div class="resume"><div class="resume-tete"><b>Ce que prévoit le texte</b><span class="tag-ia" title="Résumé rédigé automatiquement par une intelligence artificielle à partir des articles du texte déposé, sans relecture humaine">Résumé par IA</span></div><p>' + esc(s.resume.resume) + '</p><p class="note">D\'après les articles du texte déposé, qui ont pu être modifiés pendant les débats. Rédigé automatiquement, sans relecture humaine : seul <a href="' + AN + "/dyn/17/dossiers/" + esc(s.dossier) + '" target="_blank" rel="noopener">le texte officiel</a> fait foi. <a href="https://github.com/qui-vote-quoi-app/qui-vote-quoi/issues/new?template=retrait.yml&title=' + encodeURIComponent("Résumé du texte, scrutin n° " + s.num) + '" target="_blank" rel="noopener">Demander le retrait</a></p></div>' : "") +
        (s.bref ? '<p class="bref"><b>Ce que signifie ce vote.</b> ' + esc(s.bref) + "</p>" : "") + "</div>" +
      '<span class="stamp ' + (ok ? "ok" : "ko") + '">' + esc(s.sort_libelle || (ok ? "Adopté" : "Rejeté")) + "</span></div>" +
      '<div class="links">' + liens + "</div>" +
      '<div class="counts"><div><b>' + s.votants + '</b><span class="k">' + terme("votants", "votants") + '</span></div><div><b>' + s.exprimes + '</b><span class="k">' + terme("exprimes", "suffrages exprimés") + '</span></div><div><b>' + s.requis + '</b><span class="k">' + terme("requis", "majorité requise") + '</span></div>' +
      '<div><b style="color:var(--pour)">' + s.pour + '</b><span class="k">pour</span></div><div><b style="color:var(--contre)">' + s.contre + '</b><span class="k">contre</span></div><div><b style="color:var(--abst)">' + s.abst + '</b><span class="k">' + terme("abst", "abstentions") + '</span></div></div>' +
      barre({ pour: s.pour, contre: s.contre, abst: s.abst, nv: s.nv }) + focus;
    $("cbig").textContent = ok ? "Adopté" : "Rejeté"; $("cbig").setAttribute("class", "center-big " + (ok ? "ok" : "ko"));
    $("cbig").style.fill = ok ? "var(--pour)" : "var(--contre)";
    $("csub").textContent = s.pour + " pour · " + s.contre + " contre · " + s.abst + " abst.";
  }
  function rendreGroupes() {
    var s = st.s;
    $("chips").innerHTML = '<button class="chip" type="button" data-po="" aria-pressed="' + !st.grp + '">Tous</button>' +
      s.groupes.map(function (g) { var gi = st.groupes[g.po] || {}; return '<button class="chip" type="button" data-po="' + g.po + '" aria-pressed="' + (st.grp === g.po) + '"><i class="sq" style="background:' + esc(gi.couleur) + '"></i>' + esc(gi.sigle || g.po) + "</button>"; }).join("");
    $("gtb").innerHTML = s.groupes.map(function (g) {
      var gi = st.groupes[g.po] || {}, d = g.decompte, votants = d.pour + d.contre + d.abst;
      var cle = { pour: "pour", contre: "contre", abstention: "abst" }[g.position];
      return '<tr tabindex="0" data-po="' + g.po + '" class="' + (st.grp === g.po ? "on" : "") + '"><td><span class="grp"><i class="sq" style="background:' + esc(gi.couleur) + ';margin:0"></i>' + esc(gi.libelle || g.po) + ' <span class="num" style="color:var(--muted)">' + esc(gi.sigle || "") + "</span></span></td>" +
        "<td>" + (cle && votants ? '<span class="pill ' + cle + '">' + LABEL[cle] + '</span> <span class="num note">' + d[cle] + "/" + g.membres + "</span>" : '<span class="note">—</span>') + "</td>" +
        '<td class="n">' + d.pour + '</td><td class="n">' + d.contre + '</td><td class="n">' + d.abst + '</td><td class="n">' + d.nv + "</td><td>" + barre(d) + "</td></tr>";
    }).join("");
  }
  function rendreDebat() {
    var s = st.s, syn = s.synthese, el = $("debate"), h = '<div class="debate-head"><h2>Le débat en bref</h2>' + (syn && syn.seance_jour ? '<span class="note">D\'après le compte rendu de la séance du ' + esc(syn.seance_jour) + "</span>" : "") + "</div>";
    var vide = function (t) { el.innerHTML = h + '<p class="empty-deb">' + t + "</p>"; };
    if (s.categorie.cle !== "ensemble") return vide("La synthèse des débats est réservée aux votes sur l'ensemble d'un texte. Les liens ci-dessus permettent de remonter au texte et à la séance.");
    if (s.synthese_statut === "retiree") return vide("La synthèse de ce vote a été retirée à la suite d'un signalement.");
    if (s.synthese_statut === "en_attente") return vide("Synthèse en attente : elle sera générée dès la publication du compte rendu de la séance, en général sous un à deux jours.");
    if (!syn) return vide("Pas de synthèse disponible pour ce vote. Le compte rendu intégral est accessible depuis la page du scrutin sur le site de l'Assemblée.");
    var arg = function (a) {
      var d = a.dep != null ? st.deps[a.dep] : null, gi = d ? st.groupes[d.groupe] || {} : {};
      return '<div class="arg"><p>' + esc(a.resume) + "</p><blockquote>« " + esc(a.citation) + " »</blockquote>" +
        '<div class="by">— ' + (d ? '<button type="button" data-dep="' + a.dep + '">' + esc(a.nom) + "</button>" + (gi.sigle ? " (" + esc(gi.sigle) + ")" : "") : esc(a.nom) + (a.qualite ? ", " + esc(a.qualite) : "")) + "</div></div>";
    };
    var videCamp = '<p class="vide">Aucun.e orateur.rice n\'a défendu cette position lors des explications de vote.</p>';
    el.innerHTML = h + '<div class="deb-intro"><p class="context">' + esc(syn.contexte) + "</p>" +
      '<div class="ia"><b>Généré par IA</b><span>Cette synthèse est produite automatiquement par une intelligence artificielle à partir du compte rendu officiel, <strong>sans relecture humaine</strong>. Les citations sont vérifiées mot pour mot ; les résumés en gras ne sont attribués à personne. En cas d\'erreur, <a href="' + REPO + "/issues/new?template=erreur.yml&title=" + encodeURIComponent("Synthèse du scrutin n° " + s.num) + '" target="_blank" rel="noopener">signalez-la</a>.</span></div></div>' +
      '<div class="cols"><div class="col pour"><h3>Arguments pour le texte</h3>' + (syn.pour.length ? syn.pour.map(arg).join("") : videCamp) + "</div>" +
      '<div class="col contre"><h3>Arguments contre le texte</h3>' + (syn.contre.length ? syn.contre.map(arg).join("") : videCamp) + "</div></div>" +
      '<p class="note" style="margin:0">Modèle : ' + esc(syn.modele) + " · généré le " + esc((syn.genere_le || "").slice(0, 10)) + "</p>";
  }
  function rendreFiche() {
    var el = $("card");
    if (st.sel == null) {
      el.innerHTML = '<div class="eyebrow">Fiche député.e</div><p style="margin:0;color:var(--muted);font-size:14px">Cliquez sur un siège, sur un.e orateur.rice du débat, ou cherchez un nom pour afficher sa fiche.</p>';
      return;
    }
    var d = st.deps[st.sel], info = null, place = null;
    Object.keys(st.seatInfo).forEach(function (p) { if (st.seatInfo[p].dep === st.sel) { info = st.seatInfo[p]; place = p; } });
    var gVote = info ? st.groupes[info.po] || {} : null, gAct = st.groupes[d.groupe] || {};
    var pos = info ? info.pos : null;
    var groupeVote = info ? st.s.groupes.filter(function (g) { return g.po === info.po; })[0] : null;
    var maj = groupeVote ? { pour: "pour", contre: "contre", abstention: "abst" }[groupeVote.position] : null;
    var texte = !pos ? "Aucun vote enregistré pour " + (d.civ === "Mme" ? "cette députée" : "ce député") + " sur ce scrutin." : pos === "nv" ? (d.civ === "Mme" ? "Non-votante" : "Non-votant") + " sur ce scrutin." : (pos === maj ? "A voté comme la majorité de son groupe." : "A voté différemment de la majorité de son groupe.");
    el.innerHTML = '<button class="close" type="button" id="xclose" aria-label="Fermer la fiche">Fermer</button>' +
      '<div class="idt">' + avatar(d, "lg", gAct.couleur) + '<div style="min-width:0"><div class="eyebrow">' + genre(d) + (d.actif ? "" : " · mandat terminé") + "</div><h3>" + esc(d.prenom + " " + d.nom) + '</h3><span class="grp"><i class="sq" style="background:' + esc(gAct.couleur) + ';margin:0"></i>' + esc(gAct.libelle || "Sans groupe") + "</span>" + (d.photo ? '<div class="credit">Photo : Assemblée nationale</div>' : "") + "</div></div>" +
      '<div><div class="eyebrow" style="margin-bottom:6px">Ce scrutin</div>' + (pos ? '<span class="pill ' + pos + '">' + LABEL[pos] + "</span>" : "") + '<div class="note" style="margin-top:4px">' + texte + (gVote && info.po !== d.groupe ? " Groupe au moment du vote : " + esc(gVote.sigle) + "." : "") + "</div></div>" +
      "<dl><dt>Circonscription</dt><dd>" + esc(d.dept || "—") + (d.circo ? " (" + ord(d.circo) + ")" : "") + '</dd><dt>Place</dt><dd class="num">n° ' + esc(place || d.place || "—") + "</dd></dl>" +
      '<div class="card-actions"><a class="btn plein" href="#d-' + esc(d.id) + '">Historique de ses votes →</a><a class="btn" href="' + AN + "/dyn/deputes/" + esc(d.id) + '" target="_blank" rel="noopener">Fiche officielle ' + EXT + "</a></div>";
    $("xclose").onclick = function () { choisir(null); };
  }
  function montrerTip(place) {
    var info = st.seatInfo[place]; if (!info) return;
    var d = st.deps[info.dep], g = st.groupes[info.po] || {};
    tip.innerHTML = '' + avatar(d, "", g.couleur) + '<div><div class="who">' + esc(d.prenom + " " + d.nom) + '</div><div class="sub"><i class="sq" style="background:' + esc(g.couleur) + '"></i>' + esc(g.sigle || "") + " · " + esc(d.dept || "") + '</div><span class="pill ' + info.pos + '" style="margin-top:3px">' + LABEL[info.pos] + "</span></div>";
    var r = circles[place].getBoundingClientRect(), h = hemi.getBoundingClientRect();
    var x = Math.max(130, Math.min(h.width - 130, r.left + r.width / 2 - h.left + hemi.scrollLeft)), y = r.top - h.top;
    tip.style.left = x + "px"; tip.style.top = y + "px"; tip.style.transform = y < 70 ? "translate(-50%," + (r.height + 14) + "px)" : ""; tip.hidden = false;
  }
  function choisir(dep) {
    st.sel = dep; tip.hidden = true; peindre(); rendreFiche();
    if (dep != null && window.matchMedia("(max-width:1180px)").matches) $("card").scrollIntoView({ behavior: "smooth", block: "nearest" });
  }
  function filtrerGroupe(po) { st.grp = po || null; peindre(); rendreSynthese(); rendreGroupes(); }

  /* ================= Vue historique (député / groupe) ================= */
  function decoder(plat, largeur) {
    var out = [], num = 0;
    for (var i = 0; i < plat.length; i += largeur) { num += plat[i]; out.push([num].concat(plat.slice(i + 1, i + largeur))); }
    return out;
  }
  function ouvrirHisto(type, id) {
    var prec = st.h;
    st.h = { type: type, id: id, lv: prec ? prec.lv : 1, theme: prec ? prec.theme : "", pos: "", q: "", limite: PAGE, lignes: null };
    rendreHistoEntete();
    $("h-liste").hidden = false;
    $("h-liste").innerHTML = '<p class="loading">Chargement de l\'historique…</p>';
    var p;
    if (type === "d") {
      var i = st.depParId[id];
      p = getCache("votes_deputes/" + Math.floor(i / (st.meta.deputes_par_paquet || 50)) + ".json").then(function (b) {
        return decoder(b[String(i)] || [], 2).map(function (l) { return { num: l[0], pos: POS[l[1]] }; });
      });
    } else {
      p = getCache("votes_groupes/" + id + ".json").then(function (plat) {
        return decoder(plat, 7).map(function (l) { return { num: l[0], pos: POS[l[1]], d: { pour: l[2], contre: l[3], abst: l[4], nv: l[5] }, membres: l[6] }; });
      }).catch(function () { return []; });
    }
    p.then(function (lignes) {
      if (!st.h || st.h.id !== id) return;
      lignes.sort(function (a, b) { return b.num - a.num; });
      st.h.lignes = lignes.filter(function (l) { return st.parNum[l.num]; });
      rendreHistoListe(true);
    });
    listeLaterale();
  }
  function rendreHistoEntete() {
    var h = st.h, el = $("h-head");
    if (h.type === "d") {
      var d = st.deps[st.depParId[h.id]], g = st.groupes[d.groupe] || {};
      el.innerHTML = '' + avatar(d, "xl", g.couleur) + '' +
        '<div class="h-id"><div class="eyebrow">' + genre(d) + (d.actif ? "" : " · mandat terminé") + "</div><h2>" + esc(d.prenom + " " + d.nom) + "</h2>" +
        '<div class="h-meta">' + (d.groupe ? '<a class="grp" href="#g-' + d.groupe + '"><i class="sq" style="background:' + esc(g.couleur) + ';margin:0"></i>' + esc(g.libelle || d.groupe) + "</a>" : "<span>Sans groupe</span>") +
        "<span>" + esc(d.dept || "—") + (d.circo ? " (" + ord(d.circo) + " circonscription)" : "") + "</span>" +
        (d.debut ? "<span>Mandat depuis le " + dateFr(d.debut) + (d.fin ? ", terminé le " + dateFr(d.fin) : "") + "</span>" : "") + "</div>" + (d.photo ? '<div class="credit" style="margin-top:6px">Photo : Assemblée nationale</div>' : "") + "</div>" +
        '<a class="btn" href="' + AN + "/dyn/deputes/" + esc(d.id) + '" target="_blank" rel="noopener">Fiche officielle ' + EXT + "</a>";
      document.title = d.prenom + " " + d.nom + " · Qui vote quoi ?";
    } else {
      var gr = st.groupes[h.id] || { libelle: h.id, sigle: "" }, n = 0;
      st.deps.forEach(function (x) { if (x.actif && x.groupe === h.id) n++; });
      el.innerHTML = (gr.logo ? '<span class="gbloc glogo" style="border-bottom-color:' + esc(gr.couleur || "#777") + '"><img src="data/' + esc(gr.logo) + '" alt="Logo du groupe ' + esc(gr.sigle) + '"></span>' :
        '<span class="gbloc" style="background:' + esc(gr.couleur || "#777") + '" aria-hidden="true">' + esc(gr.sigle) + "</span>") +
        '<div class="h-id"><div class="eyebrow">Groupe politique' + (gr.fin ? " · dissous le " + dateFr(gr.fin) : "") + "</div><h2>" + esc(gr.libelle) + "</h2>" +
        '<div class="h-meta">' + (n ? "<span>" + n + " député.e.s aujourd'hui</span>" : "") + (gr.debut ? "<span>Créé le " + dateFr(gr.debut) + "</span>" : "") +
        "<span>Pour chaque scrutin : la position exprimée par la majorité des votants du groupe.</span></div></div>";
      document.title = gr.libelle + " · Qui vote quoi ?";
    }
  }
  function rendreHistoListe(filtres) {
    var h = st.h, el = $("h-liste");
    if (!h || !h.lignes) return;
    var q = norm(h.q.trim()), comptes = { pour: 0, contre: 0, abst: 0, nv: 0 };
    var base = h.lignes.filter(function (l) {
      var r = st.parNum[l.num];
      if (r[3] > h.lv) return false;
      if (h.theme !== "" && String(r[5]) !== h.theme) return false;
      return !q || norm(r[7] + " " + r[0]).indexOf(q) >= 0;
    });
    base.forEach(function (l) { if (comptes[l.pos] != null) comptes[l.pos]++; });
    var vis = h.pos ? base.filter(function (l) { return l.pos === h.pos; }) : base;
    if (filtres) {
      var libPos = h.type === "d" ? "Son vote" : "Position du groupe";
      el.innerHTML = '<div class="h-filtres">' + segNiveaux("hlv", h.lv) + selectThemes("hth", h.theme) +
        '<label class="sr" for="hq">Rechercher dans l\'historique</label><input id="hq" type="search" placeholder="Rechercher un texte…" value="' + esc(h.q) + '"></div>' +
        '<div class="h-pos" id="hpos" role="group" aria-label="' + libPos + '"></div><div id="hrows"></div>';
      $("hlv").onclick = function (e) { var b = e.target.closest("button"); if (!b) return; h.lv = +b.dataset.lv; h.limite = PAGE; rendreHistoListe(true); };
      $("hth").onchange = function () { h.theme = this.value; h.limite = PAGE; rendreHistoListe(false); };
      $("hq").oninput = function () { h.q = this.value; h.limite = PAGE; rendreHistoListe(false); };
    }
    $("hpos").innerHTML = '<span class="eyebrow">' + (h.type === "d" ? "Son vote" : "Position du groupe") + "</span>" +
      [["", "Tous", base.length]].concat(POS.map(function (p) { return [p, p === "nv" && h.type === "d" ? ((st.deps[st.depParId[h.id]] || {}).civ === "Mme" ? "Non-votante" : "Non-votant") : LABEL[p], comptes[p]]; })).map(function (x) {
        return '<button type="button" class="fpos' + (x[0] ? " f-" + x[0] : "") + '" data-pos="' + x[0] + '" aria-pressed="' + (h.pos === x[0]) + '">' + x[1] + ' <span class="num">' + x[2] + "</span></button>";
      }).join("");
    $("hpos").onclick = function (e) { var b = e.target.closest("button"); if (!b) return; h.pos = b.dataset.pos; h.limite = PAGE; rendreHistoListe(false); };
    var fem = h.type === "d" && (st.deps[st.depParId[h.id]] || {}).civ === "Mme";
    var libLigne = h.type === "d" ? "Son vote" : "Le groupe";
    var lignes = vis.slice(0, h.limite).map(function (l) {
      var r = st.parNum[l.num], cat = st.idx.cats[r[2]];
      var detail = h.type === "g" ? '<span class="note num">' + l.d.pour + " pour · " + l.d.contre + " contre · " + l.d.abst + " abst. sur " + l.membres + "</span>" : "";
      return '<a class="hitem" href="#s' + r[0] + '"><span class="hdate">' + dateCourte(r[1]) + '<span class="num">n° ' + r[0] + "</span></span>" +
        '<span class="ht"><span class="hmeta"><span class="cat c-' + cat + '">' + CAT_LIB[cat] + "</span>" + (r[5] >= 0 ? "<span>" + esc(st.idx.themes[r[5]]) + "</span>" : "") + "</span>" + esc(majuscule(r[7])) + "</span>" +
        '<span class="hpos"><span class="hlab">' + libLigne + "</span>" + (l.pos ? '<span class="pill ' + l.pos + '">' + (l.pos === "nv" && fem ? "Non-votante" : l.pos === "nv" && h.type === "d" ? "Non-votant" : LABEL[l.pos]) + "</span>" : '<span class="note">—</span>') + detail + "</span>" +
        '<span class="hres"><span class="hlab">Résultat</span><span class="verdict ' + (r[4] ? "v-ok" : "v-ko") + '">' + (r[4] ? "✓ Adopté" : "✗ Rejeté") + "</span></span></a>";
    }).join("");
    $("hrows").innerHTML = '<p class="sompte">' + vis.length + " scrutin" + (vis.length > 1 ? "s" : "") + "</p>" +
      (lignes ? '<div class="hlist">' + lignes + "</div>" : '<p class="empty-deb">Aucun scrutin ne correspond à ces critères.</p>') +
      (vis.length > h.limite ? '<button class="more" id="hmore" type="button">Afficher plus (' + (vis.length - h.limite) + " restants)</button>" : "");
    var m = $("hmore"); if (m) m.onclick = function () { h.limite += PAGE; rendreHistoListe(false); };
  }
  function accueilHisto(type) {
    st.h = null;
    var eff = effectifs(), actifs = st.deps.filter(function (d) { return d.actif; });
    if (type === "g") {
      $("h-head").innerHTML = '<div class="h-id"><div class="eyebrow">Groupes politiques</div><h2>Les groupes de l\'Assemblée</h2><p class="note" style="margin:6px 0 0;font-size:14px">' +
        "Les député.e.s se rassemblent en groupes selon leurs affinités politiques. Choisissez un groupe pour voir sa position sur chaque scrutin public.</p></div>";
      var gps = Object.keys(st.groupes).filter(function (po) { return !st.groupes[po].fin && eff[po]; }).sort(function (a, b) { return st.groupes[a].ordre - st.groupes[b].ordre; });
      $("h-liste").innerHTML = '<div class="gcartes">' + gps.map(function (po) {
        var g = st.groupes[po];
        return '<a class="gcarte" href="#g-' + po + '" style="border-left-color:' + esc(g.couleur) + '">' + (g.logo ? '<span class="gc-bloc gc-logo"><img src="data/' + esc(g.logo) + '" alt="Logo du groupe ' + esc(g.sigle) + '" loading="lazy"></span>' :
          '<span class="gc-bloc" style="background:' + esc(g.couleur) + '">' + esc(g.sigle) + "</span>") +
          '<span class="gc-corps"><b>' + esc(g.libelle) + '</b><span class="note">' + eff[po] + " député.e" + (eff[po] > 1 ? ".s" : "") + " · " + Math.round(eff[po] / 5.77) + " % des sièges</span>" +
          '<span class="gc-barre"><i style="width:' + (100 * eff[po] / 577).toFixed(1) + "%;background:" + esc(g.couleur) + '"></i></span>' +
          '<span class="gc-lien">Voir ses votes →</span></span></a>';
      }).join("") + "</div>";
    } else {
      // Recherche « Trouver mon ou ma député.e » : le même formulaire que l'accueil, déplacé ici.
      $("h-head").innerHTML = '<div class="h-id h-id-large"><div class="eyebrow">Les député.e.s</div><h2>Qui est votre député.e&nbsp;?</h2>' +
        '<p class="note" style="margin:6px 0 12px;font-size:14px">Tapez votre adresse ou votre commune : on vous montre votre député.e et tous ses votes.</p><div id="h-recherche"></div></div>';
      var rech = document.querySelector(".hero-recherche");
      if (rech) $("h-recherche").appendChild(rech);
      var deps = {}; actifs.forEach(function (d) { if (d.dept) deps[d.dept] = d.num_dept || ""; });
      var cleTri = function (c) { return c === "099" ? "zzz" : c === "2A" ? "020a" : c === "2B" ? "020b" : (c.length < 3 ? "0" : "") + c; };
      var noms = Object.keys(deps).sort(function (a, b) { return cleTri(deps[a]) < cleTri(deps[b]) ? -1 : 1; });
      var gps = Object.keys(st.groupes).filter(function (po) { return !st.groupes[po].fin && eff[po]; }).sort(function (a, b) { return st.groupes[a].ordre - st.groupes[b].ordre; });
      var f = st.dfiltre || (st.dfiltre = { dept: "", grp: "", lim: 48 });
      $("h-liste").innerHTML = '<h3 class="h-sous">Parcourir les ' + actifs.length + " député.e.s</h3>" +
        '<div class="trombi-filtres"><label class="sr" for="h-dept">Département</label><select id="h-dept" class="h-dept"><option value="">Tous les départements</option>' +
        noms.map(function (n) { return '<option value="' + esc(n) + '"' + (f.dept === n ? " selected" : "") + ">" + esc(deps[n] && deps[n] !== "099" ? deps[n] + " - " + n : n) + "</option>"; }).join("") + "</select>" +
        '<div class="trombi-grp" id="h-grp" role="group" aria-label="Groupe"><button type="button" data-po="" aria-pressed="' + !f.grp + '">Tous</button>' +
        gps.map(function (po) { var g = st.groupes[po]; return '<button type="button" data-po="' + po + '" aria-pressed="' + (f.grp === po) + '"><i class="sq" style="background:' + esc(g.couleur) + '"></i>' + esc(g.sigle) + "</button>"; }).join("") + "</div></div>" +
        '<p class="sompte" id="h-compte"></p><div class="trombi" id="h-trombi"></div>';
      var rendre = function () {
        var ids = [];
        st.deps.forEach(function (d, i) { if (d.actif && (!f.dept || d.dept === f.dept) && (!f.grp || d.groupe === f.grp)) ids.push(i); });
        ids.sort(function (x, y) { var a = st.deps[x], b = st.deps[y]; return f.dept ? a.circo - b.circo : a.nom.localeCompare(b.nom, "fr") || a.prenom.localeCompare(b.prenom, "fr"); });
        $("h-compte").textContent = ids.length + (ids.length > 1 ? " député.e.s" : " député.e");
        $("h-trombi").innerHTML = ids.slice(0, f.lim).map(function (i) {
          var d = st.deps[i], g = st.groupes[d.groupe] || {};
          return '<a class="tcarte" href="#d-' + d.id + '">' + avatar(d, "lg", g.couleur) + '<b>' + esc(d.prenom + " " + d.nom) + '</b><span class="m"><i class="sq" style="background:' + esc(g.couleur) + '"></i>' + esc(g.sigle || "—") + '</span><span class="m">' + esc(d.dept || "") + (d.circo ? " · " + ord(d.circo) + " circ." : "") + "</span></a>";
        }).join("") + (ids.length > f.lim ? '<button type="button" class="more" id="h-plus">Afficher plus (' + (ids.length - f.lim) + " restant" + (ids.length - f.lim > 1 ? "s" : "") + ")</button>" : "");
        var plus = $("h-plus"); if (plus) plus.onclick = function () { f.lim += 96; rendre(); };
      };
      $("h-dept").onchange = function () { f.dept = this.value; f.lim = 48; rendre(); };
      $("h-grp").onclick = function (e) {
        var b = e.target.closest("button"); if (!b) return; f.grp = b.dataset.po; f.lim = 48;
        [].forEach.call(this.querySelectorAll("button"), function (x) { x.setAttribute("aria-pressed", x === b); }); rendre();
      };
      rendre();
    }
    $("h-liste").hidden = false;
    document.title = (type === "d" ? "Député.e.s" : "Groupes") + " · Qui vote quoi ?";
  }

  /* ================= Accueil ================= */
  function effectifs() {
    var n = {};
    st.deps.forEach(function (d) { if (d.actif && d.groupe) n[d.groupe] = (n[d.groupe] || 0) + 1; });
    return n;
  }
  function rangerRecherche() {
    var rech = document.querySelector(".hero-recherche"), hero = document.querySelector(".hero");
    if (rech && hero && rech.parentNode !== hero) hero.appendChild(rech);
  }
  function rendreAccueil() {
    var nbMaj = 0;
    st.idx.s.forEach(function (r) { if (r[3] === 1) nbMaj++; });
    var nbSyn = st.idx.s.filter(function (r) { return r[6] === "publiee"; }).length;
    $("hero-chiffres").innerHTML = "<b>" + st.idx.s.length.toLocaleString("fr-FR") + "</b> scrutins publics depuis juillet 2024 · <b>" + nbMaj + "</b> votes importants · <b>" + nbSyn + "</b> débats résumés";
    var canal = (st.meta.canal || "").replace(/^@/, "");
    if (canal) { $("hero-canal").href = "https://t.me/" + canal; $("hero-canal").target = "_blank"; $("hero-canal").rel = "noopener"; }
    $("acc-votes").innerHTML = st.idx.s.filter(function (r) { return r[3] === 1; }).slice(0, 6).map(function (r) {
      var cat = st.idx.cats[r[2]];
      return '<li><a href="#s' + r[0] + '"><span class="acc-res ' + (r[4] ? "ok" : "ko") + '">' + (r[4] ? "Adopté" : "Rejeté") + '</span>' +
        '<span class="acc-t">' + esc(majuscule(r[7])) + '</span><span class="acc-m"><span>' + dateFr(r[1]) + '</span><span class="cat c-' + cat + '">' + CAT_LIB[cat] + "</span>" +
        (r[5] >= 0 ? "<span>" + esc(st.idx.themes[r[5]]) + "</span>" : "") + (r[6] === "publiee" ? "<span>· débat résumé</span>" : "") + "</span></a></li>";
    }).join("");
    var nbt = {};
    st.idx.s.forEach(function (r) { if (r[3] === 1 && r[5] >= 0) nbt[r[5]] = (nbt[r[5]] || 0) + 1; });
    $("acc-themes").innerHTML = st.idx.themes.map(function (th, i) { return [th, i, nbt[i] || 0]; })
      .filter(function (x) { return x[2] > 0; }).sort(function (a, b) { return b[2] - a[2]; })
      .map(function (x) { return '<a class="tchip" href="#theme-' + x[1] + '">' + esc(x[0]) + ' <span class="num">' + x[2] + "</span></a>"; }).join("");
    var eff = effectifs(), total = 0;
    var gps = Object.keys(eff).sort(function (a, b) { return (st.groupes[a].ordre || 0) - (st.groupes[b].ordre || 0); });
    gps.forEach(function (po) { total += eff[po]; });
    $("acc-groupes").innerHTML = '<div class="acc-barre" aria-hidden="true">' + gps.map(function (po) { return '<span style="flex:' + eff[po] + ';background:' + esc(st.groupes[po].couleur) + '"></span>'; }).join("") + "</div>" +
      '<ul class="acc-gl">' + gps.sort(function (a, b) { return eff[b] - eff[a]; }).map(function (po) {
        var g = st.groupes[po];
        return '<li><a href="#g-' + po + '"><i class="sq" style="background:' + esc(g.couleur) + '"></i><span class="num">' + esc(g.sigle) + "</span><span>" + esc(g.libelle) + '</span><span class="num n">' + eff[po] + "</span></a></li>";
      }).join("") + "</ul>";
  }

  /* Recherche « Trouver mon député » : commune, code postal ou nom. */
  var cleDep = function (t) { return norm(t).replace(/[^a-z0-9]+/g, " ").trim().replace(/^(la|le|les) /, ""); };
  function chargerCommunes() {
    return cache.communes || (cache.communes = fetch("data/communes.json").then(function (r) { if (!r.ok) throw new Error("communes"); return r.json(); }).catch(function () { delete cache.communes; return []; }));
  }
  function carteDepute(i) {
    var d = st.deps[i], g = st.groupes[d.groupe] || {};
    return '<a class="dcarte" href="#d-' + d.id + '">' + avatar(d, "", g.couleur) + '<span style="min-width:0"><b>' + esc(d.prenom + " " + d.nom) + '</b><span class="m"><i class="sq" style="background:' + esc(g.couleur) + '"></i>' + esc(g.libelle || "Sans groupe") + "</span>" +
      '<span class="m">' + esc(d.dept || "") + (d.circo ? ", " + ord(d.circo) + " circonscription" : "") + "</span></span></a>";
  }
  function deputesDe(dept, circos) {
    var k = cleDep(dept), res = [];
    st.deps.forEach(function (d, i) { if (d.actif && cleDep(d.dept) === k && (!circos || circos.indexOf(d.circo) >= 0)) res.push(i); });
    return res.sort(function (a, b) { return st.deps[a].circo - st.deps[b].circo; });
  }
  /* Communes (repli hors ligne ou si le service d'adresses ne répond pas). */
  function chercherCommunes(brut, nq, parNom) {
    return chargerCommunes().then(function (communes) {
      var cp = /^\d{5}$/.test(brut.replace(/\s/g, "")) ? brut.replace(/\s/g, "") : null, coms = [];
      communes.forEach(function (c) { if (cp ? c[3].indexOf(cp) >= 0 : cleDep(c[0]).indexOf(nq) === 0) coms.push(c); });
      coms.sort(function (a, b) { return (cleDep(a[0]) === nq ? 0 : 1) - (cleDep(b[0]) === nq ? 0 : 1) || a[0].length - b[0].length; });
      var html = "";
      coms.slice(0, 4).forEach(function (c) { html += blocCommune(c[0], c[1], c[2], c[3]); });
      if (coms.length > 4) html += '<p class="note">' + (coms.length - 4) + " autres communes correspondent : précisez la recherche.</p>";
      return html;
    });
  }
  function blocCommune(nom, dept, circos, cps) {
    var ids = deputesDe(dept, circos);
    return '<div class="tq-bloc"><h3>' + esc(nom) + ' <span class="note">' + esc(dept) + (cps && cps.length ? " · " + esc(cps.slice(0, 3).join(", ")) + (cps.length > 3 ? "…" : "") : "") + "</span></h3>" +
      (circos.length > 1 ? '<p class="note">Cette commune est partagée entre ' + circos.length + " circonscriptions : indiquez votre adresse (numéro et rue) pour trouver la vôtre.</p>" : "") +
      (ids.length ? '<div class="dcartes">' + ids.map(carteDepute).join("") + "</div>" : '<p class="note">Aucun.e député.e en exercice trouvé.e pour cette circonscription.</p>') + "</div>";
  }

  /* Adresses : service public de géocodage de l'IGN (Géoplateforme). L'adresse tapée lui est envoyée,
     le site ne la conserve pas. Le point obtenu est situé dans les contours des circonscriptions. */
  var GEOCODAGE = "https://data.geopf.fr/geocodage/search";
  var suggestions = [];
  function chargerCircos(dep) {
    var k = "circos:" + dep;
    return cache[k] || (cache[k] = fetch("data/circos/" + dep + ".json").then(function (r) { if (!r.ok) throw new Error(dep); return r.json(); }).catch(function () { delete cache[k]; return null; }));
  }
  function dansAnneau(x, y, anneau) {
    var dedans = false;
    for (var i = 0, j = anneau.length - 1; i < anneau.length; j = i++) {
      var xi = anneau[i][0], yi = anneau[i][1], xj = anneau[j][0], yj = anneau[j][1];
      if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / (yj - yi) + xi) dedans = !dedans;
    }
    return dedans;
  }
  function circoDe(circos, x, y) {
    for (var c = 0; c < circos.length; c++) {
      for (var p = 0; p < circos[c][1].length; p++) {
        var anneaux = circos[c][1][p], dedans = false;
        anneaux.forEach(function (a) { if (dansAnneau(x, y, a)) dedans = !dedans; });
        if (dedans) return circos[c][0];
      }
    }
    return null;
  }
  function localiser(f) {
    var el = $("tq-res"), p = f.properties, x = f.geometry.coordinates[0], y = f.geometry.coordinates[1];
    var dep = String(p.context || "").split(",")[0].trim();
    el.innerHTML = '<p class="note">Recherche de la circonscription…</p>';
    var retour = '<button type="button" class="lien-btn" id="tq-retour">← Autre adresse</button>';
    chargerCircos(dep).then(function (circos) {
      var num = circos && circoDe(circos, x, y);
      var ids = num ? st.deps.map(function (d, i) { return d.actif && d.num_dept === dep && d.circo === num ? i : -1; }).filter(function (i) { return i >= 0; }) : [];
      if (ids.length) {
        var d = st.deps[ids[0]];
        el.innerHTML = '<div class="tq-bloc tq-trouve"><p class="eyebrow">' + esc(p.label) + "</p><h3>" + (ids.length > 1 ? "Vos député.e.s" : d.civ === "Mme" ? "Votre députée" : "Votre député") + ' <span class="note">' + esc(d.dept) + ", " + ord(num) + " circonscription</span></h3>" +
          '<div class="dcartes">' + ids.map(carteDepute).join("") + "</div>" + retour + "</div>";
      } else {
        el.innerHTML = '<div class="tq-bloc"><p class="note">Circonscription introuvable pour « ' + esc(p.label) + " ». Essayez une adresse complète, ou parcourez <a href=\"#deputes\">la liste des député.e.s</a>.</p>" + retour + "</div>";
      }
      var b = $("tq-retour"); if (b) b.onclick = function () { $("tq-res").innerHTML = ""; $("tq").focus(); $("tq").select(); };
    });
  }
  var TYPES_ADRESSE = { housenumber: "Adresse", street: "Rue", locality: "Lieu-dit", municipality: "Commune" };
  /* Suggestions au fil de la frappe : communes et député.e.s tout de suite (données du site),
     adresses précises dès que le service de l'IGN répond. */
  var choix = [], actif = -1, geoMinuteur, jeton = 0;
  function liste() { return $("tq-liste"); }
  function fermerListe() { liste().hidden = true; liste().innerHTML = ""; actif = -1; $("tq").setAttribute("aria-expanded", "false"); }
  function afficherListe() {
    var l = liste();
    if (!choix.length) { fermerListe(); return; }
    l.innerHTML = choix.map(function (c, i) {
      return '<li role="option" id="tq-o' + i + '" aria-selected="' + (i === actif) + '" data-i="' + i + '"><span class="tq-type">' + c.type + '</span><span class="tq-lib">' + esc(c.lib) + '</span><span class="note">' + esc(c.ctx || "") + "</span></li>";
    }).join("");
    l.hidden = false; $("tq").setAttribute("aria-expanded", "true");
    $("tq").setAttribute("aria-activedescendant", actif >= 0 ? "tq-o" + actif : "");
  }
  function choisir(c) {
    fermerListe(); var el = $("tq-res");
    if (c.dep != null) { location.hash = "#d-" + st.deps[c.dep].id; return; }
    if (c.commune) { el.innerHTML = blocCommune(c.commune[0], c.commune[1], c.commune[2], c.commune[3]); return; }
    if (c.geo) localiser(c.geo);
  }
  function suggerer(q) {
    var brut = q.trim(), nq = cleDep(brut), mon = ++jeton;
    clearTimeout(geoMinuteur);
    if (nq.length < 2) { choix = []; fermerListe(); return; }
    chargerCommunes().then(function (communes) {
      if (mon !== jeton) return;
      var cp = /^\d{5}$/.test(brut.replace(/\s/g, "")) ? brut.replace(/\s/g, "") : null, coms = [];
      communes.forEach(function (c) { if (cp ? c[3].indexOf(cp) >= 0 : cleDep(c[0]).indexOf(nq) === 0) coms.push(c); });
      coms.sort(function (a, b) { return (cleDep(a[0]) === nq ? 0 : 1) - (cleDep(b[0]) === nq ? 0 : 1) || a[0].length - b[0].length; });
      var deps = [];
      st.deps.forEach(function (d, i) { if (d.actif && cleDep(d.prenom + " " + d.nom).indexOf(nq) >= 0) deps.push(i); });
      choix = coms.slice(0, 5).map(function (c) { return { type: "Commune", lib: c[0], ctx: c[1] + (c[3][0] ? " · " + c[3][0] : ""), commune: c }; })
        .concat(deps.slice(0, 4).map(function (i) { var d = st.deps[i]; return { type: genre(d), lib: d.prenom + " " + d.nom, ctx: d.dept + (d.circo ? ", " + ord(d.circo) + " circ." : ""), dep: i }; }));
      actif = -1; afficherListe();
      // Adresse précise (chiffre ou plus de 2 mots) : on interroge le géocodeur.
      if (brut.length >= 4 && (/\d/.test(brut) && !cp || brut.split(/\s+/).length > 2)) geoMinuteur = setTimeout(function () {
        fetch(GEOCODAGE + "?limit=5&autocomplete=1&index=address&q=" + encodeURIComponent(brut)).then(function (r) { if (!r.ok) throw new Error("geo"); return r.json(); }).then(function (j) {
          if (mon !== jeton) return;
          var adr = (j.features || []).filter(function (f) { return f.geometry && f.properties && f.properties.context && f.properties.type !== "municipality"; })
            .map(function (f) { return { type: TYPES_ADRESSE[f.properties.type] || "Lieu", lib: f.properties.label, ctx: f.properties.context, geo: f }; });
          choix = adr.concat(choix).slice(0, 8); actif = -1; afficherListe();
        }).catch(function () {
          // Service d'adresses indisponible : on propose au moins la commune citée dans l'adresse.
          if (mon !== jeton || choix.length) return;
          var mots = cleDep(brut.replace(/\d+/g, " ")).split(" "), trouve = [];
          for (var k = 1; k <= Math.min(4, mots.length) && !trouve.length; k++) {
            var fin = mots.slice(-k).join(" ");
            communes.forEach(function (c) { if (cleDep(c[0]) === fin) trouve.push(c); });
          }
          choix = trouve.slice(0, 5).map(function (c) { return { type: "Commune", lib: c[0], ctx: c[1] + " · adresse précise indisponible pour le moment", commune: c }; });
          actif = -1; afficherListe();
        });
      }, 250);
    });
  }
  liste().addEventListener("mousedown", function (e) { var li = e.target.closest("li[data-i]"); if (li) { e.preventDefault(); choisir(choix[+li.dataset.i]); } });
  $("tq").addEventListener("input", function () { $("tq-res").innerHTML = ""; suggerer(this.value); });
  $("tq").addEventListener("keydown", function (e) {
    if (liste().hidden) return;
    if (e.key === "ArrowDown") { e.preventDefault(); actif = (actif + 1) % choix.length; afficherListe(); }
    else if (e.key === "ArrowUp") { e.preventDefault(); actif = (actif - 1 + choix.length) % choix.length; afficherListe(); }
    else if (e.key === "Escape") fermerListe();
  });
  $("tq").addEventListener("blur", function () { setTimeout(fermerListe, 150); });
  $("trouver").addEventListener("submit", function (e) {
    e.preventDefault();
    if (choix.length) { choisir(choix[actif >= 0 ? actif : 0]); return; }
    $("tq-res").innerHTML = '<p class="note">Aucun résultat. Vérifiez l\'orthographe, ou parcourez <a href="#deputes">la liste des député.e.s</a> par département, y compris les député.e.s des Français de l\'étranger.</p>';
  });

  /* Définitions du vocabulaire parlementaire (bulle au survol, au toucher ou au clavier). */
  var DEFS = {
    votants: "Député.e.s ayant participé au vote : pour, contre ou abstention.",
    exprimes: "Votes pour et votes contre. Les abstentions ne sont pas comptées : elles ne pèsent ni pour ni contre.",
    requis: "Nombre de voix pour nécessaire à l'adoption. Pour la plupart des votes, c'est plus de la moitié des suffrages exprimés.",
    abst: "Le ou la député.e participe au vote sans se prononcer pour ou contre.",
    nv: "Député.e enregistré.e comme ne prenant pas part au vote, par exemple la présidence de séance.",
    SPS: "Vote annoncé à l'avance, à une heure fixée, pour les textes les plus importants, afin que tous les député.e.s puissent y participer.",
    SPO: "Vote nominatif demandé pendant la séance, par un président de groupe ou le Gouvernement. Seul.e.s les député.e.s présent.e.s, ou ayant délégué leur vote, y participent.",
    motion: "Vote sur la suite de l'examen d'un texte (le rejeter d'emblée, le renvoyer en commission…), pas sur son contenu article par article.",
    ensemble: "Vote final sur le texte entier, après l'examen de tous ses articles.",
    article: "Vote sur un seul article du texte.",
    amendement: "Vote sur une modification proposée au texte.",
    censure: "Vote pour renverser le Gouvernement. Il faut la majorité absolue des député.e.s.",
    declaration: "Vote sur une déclaration présentée par le Gouvernement.",
    procedure: "Vote sur l'organisation des débats."
  };
  function terme(cle, libelle) { return DEFS[cle] ? '<button type="button" class="terme" data-def="' + cle + '">' + libelle + "</button>" : libelle; }
  var pop = $("def-pop"), popCible = null;
  function montrerDef(b) {
    popCible = b; pop.textContent = DEFS[b.dataset.def]; pop.hidden = false;
    var r = b.getBoundingClientRect(), w = Math.min(300, window.innerWidth - 32);
    pop.style.width = w + "px";
    pop.style.left = Math.max(16, Math.min(r.left + window.scrollX, window.scrollX + window.innerWidth - w - 16)) + "px";
    pop.style.top = (r.bottom + window.scrollY + 8) + "px";
    b.setAttribute("aria-expanded", "true");
  }
  function cacherDef() { if (popCible) popCible.setAttribute("aria-expanded", "false"); popCible = null; pop.hidden = true; }
  document.addEventListener("click", function (e) {
    var b = e.target.closest(".terme");
    if (b) { e.preventDefault(); if (popCible === b) cacherDef(); else montrerDef(b); } else if (!e.target.closest("#def-pop")) cacherDef();
  });
  document.addEventListener("mouseover", function (e) { var b = e.target.closest && e.target.closest(".terme"); if (b && matchMedia("(hover:hover)").matches) montrerDef(b); });
  document.addEventListener("mouseout", function (e) { var b = e.target.closest && e.target.closest(".terme"); if (b && matchMedia("(hover:hover)").matches) cacherDef(); });
  document.addEventListener("focusin", function (e) { var b = e.target.closest && e.target.closest(".terme"); if (b) montrerDef(b); });
  document.addEventListener("focusout", function (e) { if (e.target.closest && e.target.closest(".terme")) cacherDef(); });
  window.addEventListener("scroll", function () { if (popCible && !matchMedia("(hover:hover)").matches) cacherDef(); }, { passive: true });

  /* ================= Navigation ================= */
  var app = $("app"), mq = window.matchMedia("(max-width:900px)");
  /* Page gardée en cache par le navigateur après une mise en ligne : on recharge une fois la dernière version. */
  (function () {
    var m = document.querySelector('meta[name="qvq-version"]'), local = m && m.content;
    if (!local || local === "dev") return;
    fetch("version.txt", { cache: "no-store" }).then(function (r) { return r.ok ? r.text() : ""; }).then(function (v) {
      v = v.trim();
      var cle = "qvq-recharge-" + v;
      if (v && v !== local) {
        try { if (sessionStorage.getItem(cle)) return; sessionStorage.setItem(cle, "1"); } catch (e) { return; }
        location.reload();
      }
    }).catch(function () {});
  })();
  function modeLateral() { return st.vue === "accueil" ? "scrutins" : st.vue; }
  function definirVue(v) {
    rangerRecherche();
    if (st.vue !== v) {
      var avant = st.vue && modeLateral();
      st.vue = v;
      app.classList.toggle("accueil", v === "accueil");
      $("side-titre").textContent = { scrutins: "Scrutins", accueil: "Scrutins", deputes: "Député.e.s", groupes: "Groupes", infos: "Le site" }[v];
      if (avant !== modeLateral()) outilsLateraux();
    }
    [].forEach.call(document.querySelectorAll(".tabs a"), function (a) { if (a.dataset.vue === v) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); });
    $("vue-scrutin").hidden = v !== "scrutins";
    $("vue-sliste").hidden = true;
    $("vue-histo").hidden = v !== "deputes" && v !== "groupes";
    $("vue-page").hidden = v !== "infos";
    $("vue-accueil").hidden = v !== "accueil";
  }
  function ouvrirPage(id) {
    st.page = id;
    listeLaterale();
    var titre = PAGES.filter(function (p) { return p[0] === id; })[0][1];
    document.title = titre + " · Qui vote quoi ?";
    var el = $("vue-page");
    var p = cache["page:" + id] || (cache["page:" + id] = fetch("pages/" + id + ".html?v=" + encodeURIComponent(VERSION)).then(function (r) { if (!r.ok) throw new Error(id); return r.text(); }));
    p.then(function (html) {
      if (st.page !== id) return;
      el.innerHTML = '<div class="panel doc"><article class="prose">' + html + '</article><aside class="doc-aside" aria-label="Sur cette page"></aside></div>';
      var titres = el.querySelectorAll(".prose h2"), aside = el.querySelector(".doc-aside");
      if (titres.length > 1) {
        aside.innerHTML = '<p class="eyebrow">Sur cette page</p><ol>' + [].map.call(titres, function (h, i) {
          return '<li><button type="button" data-sec="' + i + '">' + esc(h.textContent) + "</button></li>";
        }).join("") + '</ol><p class="doc-aide">Une question, une erreur ? <a href="#contact">Contact</a></p>';
        aside.onclick = function (e) {
          var b = e.target.closest("button[data-sec]"); if (!b) return;
          titres[+b.dataset.sec].scrollIntoView({ behavior: "smooth", block: "start" });
        };
      } else aside.remove();
      var canal = (st.meta.canal || "").replace(/^@/, "");
      [].forEach.call(el.querySelectorAll("[data-si-canal]"), function (x) { x.hidden = !canal; });
      [].forEach.call(el.querySelectorAll("[data-sans-canal]"), function (x) { x.hidden = !!canal; });
      [].forEach.call(el.querySelectorAll("a[data-canal]"), function (x) { x.href = (x.dataset.canal === "web" ? "https://t.me/s/" : "https://t.me/") + canal; });
      [].forEach.call(el.querySelectorAll("[data-canal-nom]"), function (x) { x.textContent = "@" + canal; });
      [].forEach.call(el.querySelectorAll("a[data-vers]"), function (x) {
        x.onclick = function (e) { e.preventDefault(); var c = document.getElementById(x.dataset.vers); if (c) c.scrollIntoView({ behavior: "smooth", block: "start" }); };
      });
      var cl = el.querySelector("[data-credits-logos]");
      if (cl) cl.innerHTML = Object.keys(st.groupes).filter(function (po) { return st.groupes[po].logo; }).map(function (po) {
        var g = st.groupes[po]; return "<li><b>" + esc(g.sigle) + "</b> : " + esc(g.logo_credit) + "</li>";
      }).join("") || "<li>Aucun logo affiché pour le moment.</li>";
      var fil = el.querySelector("[data-fil]");
      if (fil) getCache("fil.json").then(function (F) {
        fil.innerHTML = (F || []).length ? F.map(function (j) {
          var d = new Date(j.date + "T12:00:00");
          return '<article class="tg-bulle tg-msg"><p><b>🏛 À L\'ASSEMBLÉE · ' + esc(d.toLocaleDateString("fr-FR", { day: "numeric", month: "long" }).toUpperCase()) + "</b><br>" + j.n + " vote" + (j.n > 1 ? "s importants" : " important") + "</p>" + j.html.split("\n\n").map(function (b) { return "<p>" + b.replace(/\n/g, "<br>") + "</p>"; }).join("") + "</article>";
        }).join("") : '<p class="note">Aucun message pour le moment.</p>';
      }, function () { fil.innerHTML = '<p class="note">Les messages n\'ont pas pu être chargés.</p>'; });
      var ap = el.querySelector("img[data-apercu]");
      var A = st.meta.apercu;
      if (ap) { if (A) ap.src = "data/apercu.png?v=" + encodeURIComponent(VERSION); else ap.closest("figure").hidden = true; }
      var cap = el.querySelector("[data-apercu-texte]");
      if (cap && A) cap.innerHTML = (A.adopte ? "✅ " : "❌ ") + "<b>" + esc(majuscule(A.titre)) + "</b> · " + (A.adopte ? "adopté" : "rejeté") + '<blockquote class="tg-cit">' + esc(A.bref) + "</blockquote>" +
        A.pour + " pour · " + A.contre + " contre · " + A.abst + " abst.<br>" + '<span class="tg-boutons"><a href="#s' + A.num + '">🔎 Qui a voté quoi</a></span>';
      var b = $("copier-adresse");
      if (b) b.onclick = function () {
        var a = $("adresse").textContent;
        var ok = function () { b.textContent = "Copié"; setTimeout(function () { b.textContent = "Copier"; }, 1500); };
        try { navigator.clipboard.writeText(a).then(ok, function () { getSelection().selectAllChildren($("adresse")); }); }
        catch (e) { getSelection().selectAllChildren($("adresse")); }
      };
    }).catch(function () { delete cache["page:" + id]; el.innerHTML = '<article class="panel prose"><p>Cette page n\'a pas pu être chargée. Réessayez dans quelques instants.</p></article>'; });
  }
  function route() {
    var h = location.hash, m;
    fermerMobile();
    if ((m = /^#s(\d+)$/.exec(h))) { definirVue("scrutins"); ouvrirScrutin(+m[1]); }
    else if ((m = /^#d-(PA\d+)$/.exec(h)) && st.depParId[m[1]] != null) { definirVue("deputes"); ouvrirHisto("d", m[1]); }
    else if ((m = /^#g-(PO\d+)$/.exec(h))) { definirVue("groupes"); ouvrirHisto("g", m[1]); }
    else if (h === "#deputes") { definirVue("deputes"); accueilHisto("d"); listeLaterale(); }
    else if (h === "#groupes") { definirVue("groupes"); accueilHisto("g"); listeLaterale(); }
    else if (PAGES.some(function (p) { return "#" + p[0] === h; })) { definirVue("infos"); ouvrirPage(h.slice(1)); }
    else if ((m = /^#theme-(\d+)$/.exec(h)) && st.idx.themes[+m[1]]) {
      var maj1 = st.idx.s.filter(function (x) { return String(x[5]) === m[1] && x[3] === 1; })[0];
      var r = maj1 || st.idx.s.filter(function (x) { return String(x[5]) === m[1]; })[0];
      st.f.theme = m[1]; st.f.lv = maj1 ? 1 : 3; st.limite = PAGE; st.vue = null; definirVue("scrutins");
      if (r) ouvrirScrutin(r[0]); listeLaterale();
    }
    else if (h === "#scrutins") { definirVue("scrutins"); accueilScrutins(); ouvrirListe(); }
    else { definirVue("accueil"); rendreAccueil(); listeLaterale(); document.title = "Qui vote quoi ? · Les votes de l'Assemblée nationale"; }
    if (st.vue === "scrutins") centrerHemicycle();
    window.scrollTo(0, 0);
  }
  function miniHemi(sieges) {
    var c = { "0": "pour", "1": "contre", "2": "abst", "3": "nv" }, out = "";
    Object.keys(st.places).forEach(function (num) {
      var p = st.places[num], k = sieges.charAt(+num);
      out += '<circle cx="' + p[0].toFixed(1) + '" cy="' + p[1].toFixed(1) + '" r="1.75" class="' + (c[k] || "vide") + '"/>';
    });
    return '<svg class="mhemi" viewBox="4 3 229 127" aria-hidden="true">' + out + "</svg>";
  }
  function accueilScrutins() {
    $("vue-scrutin").hidden = true; $("vue-sliste").hidden = false; st.num = null;
    document.title = "Scrutins · Qui vote quoi ?"; listeLaterale();
    getCache("derniers.json").then(function (L) {
      $("scartes").innerHTML = (L || []).map(function (r) {
        var cat = st.idx.cats[r[2]];
        return '<a class="scarte" href="#s' + r[0] + '">' + miniHemi(r[9]) +
          '<span class="sc-res ' + (r[3] ? "ok" : "ko") + '">' + (r[3] ? "✓ Adopté" : "✗ Rejeté") + '</span>' +
          '<span class="sc-meta">' + "<span>" + esc(dateCourte(r[1])) + '</span><span class="cat c-' + cat + '">' + CAT_LIB[cat] + "</span>" + (r[8] ? "<span>" + esc(r[8]) + "</span>" : "") + "</span>" +
          '<b class="sc-titre">' + esc(r[7]) + "</b>" +
          '<span class="sc-chiffres num">' + r[4] + " pour · " + r[5] + " contre" + (r[6] ? " · " + r[6] + " abst." : "") + "</span></a>";
      }).join("") || '<p class="note">Aucun vote important pour le moment.</p>';
    }, function () { $("scartes").innerHTML = '<p class="note">La liste n\'a pas pu être chargée.</p>'; });
  }
  function premierMajeur() {
    var r = st.idx.s.filter(function (x) { return x[3] === 1; })[0] || st.idx.s[0];
    return r ? r[0] : st.meta.dernier;
  }
  function majBouton() {
    var ouvert = mq.matches ? app.classList.contains("mopen") : !app.classList.contains("collapsed");
    $("toggle").setAttribute("aria-expanded", ouvert);
    $("toggle").setAttribute("aria-label", ouvert ? "Replier la liste" : "Déplier la liste");
  }
  function ouvrirListe() {
    if (mq.matches) setTimeout(ouvrirMobile, 0);
    else if (app.classList.contains("collapsed")) { app.classList.remove("collapsed"); majBouton(); }
  }
  function ouvrirMobile() { app.classList.add("mopen"); majBouton(); }
  function fermerMobile() { if (app.classList.contains("mopen")) { app.classList.remove("mopen"); majBouton(); } }
  $("toggle").onclick = function () {
    if (mq.matches) app.classList.toggle("mopen");
    else { var c = app.classList.toggle("collapsed"); try { localStorage.setItem("qvq-side", c ? "1" : "0"); } catch (e) {} }
    majBouton();
  };
  try { if (localStorage.getItem("qvq-side") === "1") app.classList.add("collapsed"); } catch (e) {}
  if (mq.addEventListener) mq.addEventListener("change", majBouton);
  majBouton();

  /* Thème : Auto → Clair → Sombre */
  var THEMES = [["auto", "Auto"], ["light", "Clair"], ["dark", "Sombre"]];
  function appliquerTheme(t) {
    if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t);
    else { document.documentElement.removeAttribute("data-theme"); t = "auto"; }
    var lib = THEMES.filter(function (x) { return x[0] === t; })[0][1];
    $("theme-libelle").textContent = lib;
    $("theme").setAttribute("aria-label", "Thème d'affichage : " + lib + ". Changer");
    try { if (t === "auto") localStorage.removeItem("qvq-theme"); else localStorage.setItem("qvq-theme", t); } catch (e) {}
  }
  $("theme").onclick = function () {
    var cur = document.documentElement.getAttribute("data-theme") || "auto";
    var i = THEMES.findIndex(function (x) { return x[0] === cur; });
    appliquerTheme(THEMES[(i + 1) % THEMES.length][0]);
  };
  appliquerTheme(document.documentElement.getAttribute("data-theme") || "auto");

  /* Événements de la vue scrutin */
  svg.addEventListener("pointerover", function (e) { var p = e.target.dataset && e.target.dataset.place; if (p && e.pointerType !== "touch") montrerTip(p); });
  svg.addEventListener("pointerout", function (e) { if (e.target.dataset && e.target.dataset.place) tip.hidden = true; });
  svg.addEventListener("click", function (e) { var p = e.target.dataset && e.target.dataset.place; if (p && st.seatInfo[p]) choisir(st.seatInfo[p].dep); });
  $("debate").addEventListener("click", function (e) { var b = e.target.closest("button[data-dep]"); if (b) { choisir(+b.dataset.dep); hemi.scrollIntoView({ behavior: "smooth", block: "center" }); } });
  $("chips").addEventListener("click", function (e) { var b = e.target.closest(".chip"); if (b) filtrerGroupe(b.dataset.po); });
  $("gtb").addEventListener("click", function (e) { var r = e.target.closest("tr"); if (r) filtrerGroupe(st.grp === r.dataset.po ? null : r.dataset.po); });
  $("gtb").addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { var r = e.target.closest("tr"); if (r) { e.preventDefault(); filtrerGroupe(st.grp === r.dataset.po ? null : r.dataset.po); } } });
  $("q").addEventListener("change", function () {
    var v = norm(this.value), i = st.deps.findIndex(function (d) { return norm(d.prenom + " " + d.nom) === v; });
    if (i >= 0) { choisir(i); this.value = ""; }
  });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") { if (app.classList.contains("mopen")) fermerMobile(); else if (st.sel != null) choisir(null); } });
  window.addEventListener("hashchange", route);

  /* ================= Démarrage ================= */
  get("meta.json").then(function (meta) {
    st.meta = meta; VERSION = meta.maj_site || "";
    return Promise.all([get("index.json"), get("groupes.json"), get("deputes.json"), get("places.json")]);
  }).then(function (r) {
    st.idx = r[0]; st.groupes = r[1]; st.deps = r[2]; st.places = r[3].places;
    st.idx.s.forEach(function (x) { st.parNum[x[0]] = x; });
    st.deps.forEach(function (d, i) { st.depParId[d.id] = i; });
    dessinerSieges();
    $("dl").innerHTML = st.deps.filter(function (d) { return d.actif; }).map(function (d) { return '<option value="' + esc(d.prenom + " " + d.nom) + '">'; }).join("");
    var src = (st.meta.sources || {}).scrutins;
    var maj = "";
    if (src) { var dt = new Date(src); maj = isNaN(dt) ? esc(src) : dt.toLocaleDateString("fr-FR", { day: "numeric", month: "long", year: "numeric" }); }
    $("footer").innerHTML =
      '<nav class="foot-nav" aria-label="Informations sur le site">' + PAGES.map(function (p) { return '<a href="#' + p[0] + '">' + p[1] + "</a>"; }).join("") +
      '<a href="' + REPO + '" target="_blank" rel="noopener">Code source ' + EXT + "</a></nav>" +
      '<p class="foot-info">Site indépendant, sans lien avec l\'Assemblée nationale. Données : Assemblée nationale (data.assemblee-nationale.fr), Licence Ouverte 2.0' + (maj ? ", mises à jour le " + maj : "") + ".<br>" +
      'Inspiré du travail de <a href="https://datan.fr" target="_blank" rel="noopener">Datan</a>, de <a href="' + INSPIRATION + '" target="_blank" rel="noopener">@votes_assemblee_nationale</a> et de <a href="https://www.nosdeputes.fr" target="_blank" rel="noopener">NosDéputés.fr</a>, qu\'il complète sans remplacer leur travail d\'analyse (<a href="#a-propos">à propos</a>).</p>';
    route();
  }).catch(function (e) {
    $("summary").innerHTML = '<p class="empty-deb">Les données n\'ont pas pu être chargées. Réessayez dans quelques minutes.</p>';
    console.error(e);
  });
})();
