"""Generates FICTIONAL, filled-in documents for testing the accountant agent: the ONRC registration request
(Anexa 2a), the fiscal registration request (Anexa 1, vector fiscal), the articles of association, the loan-for-use
contract for the registered office and an expense invoice. The contract deliberately gives a different apartment
number than the other documents, so the dossier review has an inconsistency to catch.
All names, CNP/CUI and IBAN values are invented. Usage: make_fictive_docs.py <output_dir>"""
import sys
from pathlib import Path

import pymupdf as fitz

FONTS = "/usr/share/fonts/truetype/dejavu"
CSS = f"""
@font-face {{ font-family: dv; src: url(DejaVuSans.ttf); }}
@font-face {{ font-family: dv; src: url(DejaVuSans-Bold.ttf); font-weight: bold; }}
@font-face {{ font-family: dvs; src: url(DejaVuSerif.ttf); }}
@font-face {{ font-family: dvs; src: url(DejaVuSerif-Bold.ttf); font-weight: bold; }}
body {{ font-family: dvs; font-size: 9pt; line-height: 1.35; }}
h1 {{ font-size: 13pt; text-align: center; margin: 4pt 0; }}
h2 {{ font-size: 10pt; margin: 8pt 0 3pt 0; }}
p {{ margin: 2pt 0; }}
.fictiv {{ font-family: dv; font-size: 8pt; color: #b00000; text-align: center; border: 1px solid #b00000; padding: 3pt; }}
.right {{ text-align: right; font-size: 8pt; }}
.small {{ font-size: 7.5pt; }}
table {{ border-collapse: collapse; width: 100%; }}
td, th {{ border: 1px solid #000; padding: 2pt 4pt; font-size: 8.5pt; vertical-align: top; }}
th {{ background: #e6e6e6; text-align: left; }}
.box {{ font-family: dv; }}
b.v {{ font-family: dv; }}
"""

X, O = "☒", "☐"
FICTIV = ("DOCUMENT FICTIV generat pentru testarea aplicației Raiff Quest — persoanele, firma, CNP, CUI și IBAN sunt inventate. "
          "Nu are valoare juridică.")

PERSON = {
    "nume": "IONESCU", "prenume": "MARIA-ELENA", "cnp": "2980412120017",
    "domiciliu": "Cluj-Napoca, str. Fabricii nr. 18, bl. C4, sc. 2, et. 3, ap. 41, jud. Cluj, România",
    "nastere": "Turda, jud. Cluj, România, la data de 12.04.1998",
    "act": "CI seria CJ nr. 784512, emisă de SPCLEP Cluj-Napoca la 05.06.2022, valabilă până la 12.04.2032",
    "email": "maria.ionescu@atelierverde-demo.ro", "telefon": "0740 123 456",
}
FIRM = {
    "nume": "ATELIER VERDE DESIGN SRL", "sediu": "Cluj-Napoca, str. Memorandumului nr. 7, et. 2, ap. 5, jud. Cluj",
    "email": "contact@atelierverde-demo.ro", "web": "www.atelierverde-demo.ro",
    "caen": "7412 – Activități de design grafic și de comunicare vizuală",
    "capital": "1.000 lei, integral vărsat (100 părți sociale × 10 lei)",
    "cui": "51987654", "iban": "RO12 RZBR 0000 0600 9876 5432",
    "nr_cerere": "218734", "data": "11.10.2026",
}


def v(text: str) -> str:
    return f"<b class='v'>{text}</b>"


def render(html: str, path: Path, extra_css: str = "") -> None:
    story = fitz.Story(html=html, user_css=CSS + extra_css, archive=fitz.Archive(FONTS))
    tmp = path.with_suffix(".tmp.pdf")
    writer = fitz.DocumentWriter(str(tmp))
    page = fitz.paper_rect("a4")
    where = page + (42, 40, -42, -40)
    more = 1
    while more:
        device = writer.begin_page(page)
        more, _ = story.place(where)
        story.draw(device)
        writer.end_page()
    writer.close()
    doc = fitz.open(tmp)
    doc.subset_fonts()
    doc.save(path, garbage=4, deflate=True)
    doc.close()
    tmp.unlink()


def onrc_request() -> str:
    p, f = PERSON, FIRM
    return f"""
<p class="fictiv">{FICTIV}</p>
<p class="right">ANEXA Nr. 2a</p>
<p><b>I. MINISTERUL JUSTIȚIEI — OFICIUL NAȚIONAL AL REGISTRULUI COMERȚULUI</b><br>
OFICIUL REGISTRULUI COMERȚULUI DE PE LÂNGĂ TRIBUNALUL {v("CLUJ")}</p>
<h1>II. CERERE<br>înregistrare în registrul comerțului — persoane juridice —</h1>
<p class="box">{X} înmatriculare &nbsp; {O} înregistrare sucursală persoană juridică română &nbsp; {O} înregistrare sucursală persoană juridică străină
&nbsp; {O} înscriere mențiuni &nbsp; {O} înscriere operațiuni comunicate de autoritatea / instituția publică &nbsp; {O} radiere
&nbsp; {O} îndreptare eroare materială &nbsp; {O} actualizare obiect de activitate conform CAEN Rev. 3</p>
<p><b>III.</b> Nr. înregistrare: {v(f["nr_cerere"])} &nbsp;&nbsp; Data: {v(f["data"])}</p>

<h2>IV. Subsemnatul(a)</h2>
<p>Nume {v(p["nume"])}, Prenume {v(p["prenume"])}, CNP {v(p["cnp"])}, domiciliat(ă) în {v(p["domiciliu"])},
cetățenia {v("română")}, născut(ă) în {v(p["nastere"])}, act identitate {v(p["act"])}, regimul matrimonial {v("necăsătorită")},
în calitate de {v("asociat unic și administrator")}, conform {v("Actului constitutiv din 08.10.2026")}.</p>
<p>În temeiul Legii nr. 265/2022 privind registrul comerțului și pentru modificarea și completarea altor acte normative cu incidență
asupra înregistrării în registrul comerțului, solicit:</p>

<h2>V. Obiectul cererii privind înregistrarea în registrul comerțului, prevăzut în {v("Actul constitutiv")}, constă în:</h2>
<p><b>1. Înmatriculare</b> pentru firma: {v(f["nume"])}, cu sediul social în: {v(f["sediu"])}, e-mail {v(f["email"])},
telefon {v(p["telefon"])}, pagina de internet {v(f["web"])}.</p>
<table>
<tr><th style="width:38%">Element</th><th>Date declarate</th></tr>
<tr><td>Formă juridică</td><td>{v("Societate cu răspundere limitată (SRL), asociat unic")}</td></tr>
<tr><td>Capital social</td><td>{v(f["capital"])}</td></tr>
<tr><td>Asociat unic / administrator</td><td>{v(p["prenume"] + " " + p["nume"])}, CNP {v(p["cnp"])}, puteri depline, mandat pe durată nelimitată</td></tr>
<tr><td>Durata de funcționare</td><td>{v("nelimitată")}</td></tr>
<tr><td>Obiect principal de activitate (CAEN Rev. 3)</td><td>{v(f["caen"])}</td></tr>
<tr><td>Activități secundare</td><td>{v("6201 – Activități de realizare a soft-ului la comandă; 7311 – Activități ale agențiilor de publicitate; 8559 – Alte forme de învățământ")}</td></tr>
<tr><td>Activități desfășurate</td><td>{v("la sediul social și în afara acestuia, la beneficiari, fără punct de lucru")}</td></tr>
<tr><td>Act de spațiu pentru sediul social</td><td>{v("Contract de comodat nr. 12 din 01.10.2026, valabil până la 30.09.2029")}</td></tr>
<tr><td>Beneficiar real</td><td>{v(p["prenume"] + " " + p["nume"] + " — 100% din părțile sociale")}</td></tr>
</table>
<p class="box"><b>4.3.</b> {X} Declarație pe propria răspundere cu privire la îndeplinirea condițiilor de funcționare (pentru sediul social).</p>
<p class="box"><b>4.2.</b> {X} Dovadă vărsământ capital social &nbsp; {O} Prospect de emisiune acțiuni &nbsp; {O} Hotărâre AGA &nbsp; {O} Situații financiare</p>

<h2>VI. Solicit:</h2>
<p class="box">{O} audiență publică &nbsp; {O} copii &nbsp; {X} copii certificate de pe documentele {v("certificat de înregistrare, act constitutiv")}<br>
comunicarea documentelor care atestă efectuarea înregistrării: {O} poștă &nbsp; {O} curier &nbsp; {X} mijloace electronice &nbsp; {O} sediul O.R.C.T.</p>

<h2>VII. Persoana pentru comunicare</h2>
<p>Nume {v(p["nume"])}, Prenume {v(p["prenume"])}, adresa {v(p["domiciliu"])}, cod poștal {v("400394")},
telefon {v(p["telefon"])}, e-mail {v(p["email"])}.</p>

<h2>VIII. Date de facturare</h2>
<p>Nume și prenume / firmă {v(p["prenume"] + " " + p["nume"])}, CNP {v(p["cnp"])}, e-mail {v(p["email"])},
Banca {v("Raiffeisen Bank S.A.")}, CONT IBAN {v("RO98 RZBR 0000 0600 1122 3344")}, Adresa {v(p["domiciliu"])}.</p>

<h2>IX. OPIS DE DOCUMENTE DEPUSE</h2>
<table>
<tr><th>Nr. crt.</th><th>Denumirea actului — Nr. și data actului / Emitent</th><th>Nr. file</th></tr>
<tr><td>1.</td><td>Act constitutiv al societății (asociat unic) — din 08.10.2026 / asociatul unic</td><td>6</td></tr>
<tr><td>2.</td><td>Dovada rezervării denumirii — nr. 0918273 din 02.10.2026 / ONRC</td><td>1</td></tr>
<tr><td>3.</td><td>Contract de comodat pentru sediul social — nr. 12 din 01.10.2026 / Pop Andrei (proprietar)</td><td>3</td></tr>
<tr><td>4.</td><td>Dovadă vărsământ capital social — OP din 09.10.2026 / Raiffeisen Bank</td><td>1</td></tr>
<tr><td>5.</td><td>Declarație pe propria răspundere a asociatului unic și administratorului — din 08.10.2026</td><td>2</td></tr>
<tr><td>6.</td><td>Declarație privind beneficiarul real — din 08.10.2026</td><td>1</td></tr>
<tr><td>7.</td><td>Cerere de înregistrare fiscală (Anexa 1) — din 11.10.2026</td><td>1</td></tr>
<tr><td colspan="2"><b>Total file:</b></td><td><b>15</b></td></tr>
</table>

<h2>X. Prelucrarea datelor cu caracter personal</h2>
<p>Am fost informat cu privire la prelucrarea datelor cu caracter personal efectuată în scopul soluționării prezentei cereri.<br>
{v(p["prenume"] + " " + p["nume"])} &nbsp;&nbsp; {v(f["data"])} &nbsp;&nbsp; Semnătura: {v("M. Ionescu")}</p>
<p><b>XI.</b> Anexele nr. {v("1 (cererea de înregistrare fiscală)")} fac parte integrantă din prezenta cerere.<br>
Întocmită într-un exemplar, pe propria răspundere, cunoscând că declarațiile inexacte sunt pedepsite conform legii.<br>
Data {v(f["data"])} &nbsp;&nbsp; Semnătura {v("M. Ionescu")}</p>
<p><b>XII.</b> Cererea se depune de către semnatar (nu prin împuternicit).</p>
<p class="small">Note: (1) Reprezentantul legal al persoanei juridice sau împuternicitul acestuia. (3) Solicitantul depune, odată cu cererea,
declarația pe propria răspundere cu privire la îndeplinirea condițiilor de funcționare. (9) Factura fiscală se emite pentru persoana indicată.</p>
"""


def fiscal_request() -> str:
    p, f = PERSON, FIRM

    def row(label, checked=None, date=None):
        box = "" if checked is None else (X if checked else O)
        value = f": &nbsp; {v(date)}" if date else ""
        return f"<tr><td>{label}{value}</td><td class='box'>{box}</td></tr>"

    def section(title, checked):
        return f"<tr><th><i>{title}</i></th><th class='box'>{X if checked else O}</th></tr>"

    start = "01/11/2026"
    return f"""
<p class="fictiv">{FICTIV}</p>
<p class="right"><u>ANEXĂ*)</u><br><i>(Anexa nr. 1 la Ordinul nr. 2.509/5.672/C/2022 —<br>Anexă la Cererea de înregistrare în registrul comerțului)</i></p>
<h1>Cerere de înregistrare fiscală</h1>
<p>Nr. {v(f["nr_cerere"])} &nbsp;&nbsp; Data {v(f["data"])} &nbsp;&nbsp;&nbsp;&nbsp;
<span class="box">{X} Persoană juridică &nbsp; {O} Persoană fizică</span></p>
<p>Denumire: {v(f["nume"])} &nbsp; Sediu social: {v(f["sediu"])}</p>
<table>
<tr><th colspan="2">DATE PRIVIND VECTORUL FISCAL</th></tr>
{section("1. Impozit pe profit", False)}
{row("1.1. Luare în evidență începând cu data de")}
{row("1.2. Perioada fiscală: &nbsp; 1.2.1. Trimestrială ☐ &nbsp;&nbsp; 1.2.2. Anuală", False)}
{section("2. Impozit pe veniturile microîntreprinderilor", True)}
{row("2.1. Luare în evidență începând cu data de", None, start)}
{section("3. Impozit pe veniturile din salarii și asimilate salariilor, precum și contribuții sociale", True)}
<tr><td colspan="2"><i>3.1. Informații pentru stabilirea perioadei fiscale</i></td></tr>
{row("3.1.1. Număr mediu de salariați estimat de până la 3 salariați exclusiv", True)}
{row("3.1.2. Venit total estimat de până la 100.000 euro", True)}
{row("3.2. Perioada fiscală: &nbsp; 3.2.1. Lunară potrivit legii ☐ &nbsp;&nbsp; 3.2.2. Trimestrială", True)}
<tr><td colspan="2"><i>3.3. Impozit pe veniturile din salarii și asimilate salariilor</i></td></tr>
{row("3.3.1. Luare în evidență începând cu data de", True, start)}
<tr><td colspan="2"><i>3.4. Contribuție de asigurări sociale (datorată de angajat)</i></td></tr>
{row("3.4.1. Luare în evidență începând cu data de", True, start)}
<tr><td colspan="2"><i>3.5. Contribuție de asigurări sociale de sănătate (datorată de angajat)</i></td></tr>
{row("3.5.1. Luare în evidență începând cu data de", True, start)}
<tr><td colspan="2"><i>3.6. Contribuție asiguratorie pentru muncă (datorată de angajator)</i></td></tr>
{row("3.6.1. Luare în evidență începând cu data de", True, start)}
{section("4. Taxa pe valoarea adăugată", False)}
<tr><td>4.1. Cifra de afaceri estimată a se realiza, conform art.310 alin.(1) din Legea nr.227/2015 privind Codul fiscal,
cu modificările și completările ulterioare: &nbsp; {v("180.000 lei")}</td><td></td></tr>
{row("4.2. Înregistrare în scopuri de TVA conform art.316 alin.(1) lit.a) pct.1 din Codul fiscal, ca urmare a declarării faptului că cifra de afaceri urmează să depășească plafonul de scutire prevăzut la art.310 alin.(1)", False)}
{row("4.3. Înregistrare prin opțiune pentru aplicarea regimului normal de TVA, conform art.316 alin.(1) lit.a) pct.2 din Codul fiscal, cifra de afaceri estimată fiind inferioară plafonului de scutire", False)}
{row("4.4. Perioada fiscală, potrivit art.322 din Codul fiscal: &nbsp; 4.4.1. Lunară ☐ &nbsp;&nbsp; 4.4.2. Trimestrială", False)}
{row("4.5. Declar pe propria răspundere că sunt persoană impozabilă eligibilă pentru aplicarea sistemului TVA la încasare și <b>optez pentru aplicarea sistemului TVA la încasare</b> începând cu data înregistrării în scopuri de TVA", False)}
</table>
<br>
<table>
<tr><td style="width:40%">Numele și prenumele persoanei care face declarația</td><td>{v(p["prenume"] + " " + p["nume"])}</td></tr>
<tr><td>Funcția</td><td>{v("Administrator")}</td></tr>
<tr><td>Semnătura</td><td>{v("M. Ionescu")}</td></tr>
<tr><td>Data</td><td>{v(f["data"].replace(".", " / "))}</td></tr>
</table>
<p><i>Atenție! În cazul în care aveți și alte obligații declarative cu caracter permanent, potrivit legii, în plus față de cele declarate
prin prezenta, aveți obligația depunerii Declarației de mențiuni la organul fiscal competent.</i></p>
<p class="small">Informații suplimentare (fictive) pentru test: un salariat estimat cu normă întreagă (administratorul), salariu brut 4.325 lei/lună
din 01.11.2026; cheltuieli estimate 3.000 lei/lună (chirie birou coworking, licențe software, contabilitate).</p>
<p class="small">*) Anexa este reprodusă în facsimil.</p>
"""


def articles_of_association() -> str:
    p, f = PERSON, FIRM
    name = p["prenume"] + " " + p["nume"]
    return f"""
<p class="fictiv">{FICTIV}</p>
<h1>ACT CONSTITUTIV<br>al societății cu răspundere limitată cu asociat unic<br>{f["nume"]}</h1>
<p>Încheiat astăzi, {v("08.10.2026")}, la Cluj-Napoca.</p>
<h2>Capitolul I. Asociatul unic</h2>
<p>Subsemnata {v(name)}, cetățean român, CNP {v(p["cnp"])}, născută în {v(p["nastere"])}, domiciliată în {v(p["domiciliu"])},
identificată cu {v(p["act"])}, în calitate de asociat unic, am hotărât constituirea unei societăți cu răspundere limitată,
în temeiul Legii societăților nr. 31/1990 și al Legii nr. 265/2022 privind registrul comerțului.</p>
<h2>Capitolul II. Denumirea, forma juridică, sediul, durata</h2>
<p><b>Art. 1.</b> Denumirea societății este {v(f["nume"])}, conform dovezii de rezervare a denumirii nr. {v("0918273 din 02.10.2026")}.</p>
<p><b>Art. 2.</b> Forma juridică: societate cu răspundere limitată, persoană juridică română.</p>
<p><b>Art. 3.</b> Sediul social este în {v(f["sediu"])}, în baza contractului de comodat nr. {v("12 din 01.10.2026")}.
Sediul poate fi schimbat prin decizia asociatului unic.</p>
<p><b>Art. 4.</b> Durata de funcționare a societății este nelimitată.</p>
<h2>Capitolul III. Obiectul de activitate</h2>
<p><b>Art. 5.</b> Domeniul și activitatea principală: {v(f["caen"])}.<br>
Activități secundare: {v("6201 – Activități de realizare a soft-ului la comandă; 7311 – Activități ale agențiilor de publicitate; 8559 – Alte forme de învățământ")}.</p>
<h2>Capitolul IV. Capitalul social</h2>
<p><b>Art. 6.</b> Capitalul social este de {v(f["capital"])}, aport în numerar, vărsat integral în contul societății deschis la
{v("Raiffeisen Bank S.A.")}, conform ordinului de plată din {v("09.10.2026")}.</p>
<p><b>Art. 7.</b> Părțile sociale nu pot fi gajate și pot fi transmise conform Legii nr. 31/1990.</p>
<h2>Capitolul V. Administrarea și controlul</h2>
<p><b>Art. 8.</b> Societatea este administrată de {v(name)}, numită administrator pe durată nelimitată, cu puteri depline de reprezentare.</p>
<p><b>Art. 9.</b> Asociatul unic exercită atribuțiile adunării generale a asociaților. Societatea nu are obligația numirii unui cenzor;
situațiile financiare anuale se întocmesc de un expert contabil autorizat.</p>
<h2>Capitolul VI. Exercițiul financiar, profitul, dividendele</h2>
<p><b>Art. 10.</b> Exercițiul financiar începe la 1 ianuarie și se încheie la 31 decembrie. Primul exercițiu începe la data înmatriculării.</p>
<p><b>Art. 11.</b> Profitul net se repartizează prin decizia asociatului unic, după constituirea rezervelor legale.</p>
<h2>Capitolul VII. Dizolvarea și lichidarea</h2>
<p><b>Art. 12.</b> Dizolvarea și lichidarea se fac în condițiile Legii nr. 31/1990.</p>
<h2>Capitolul VIII. Dispoziții finale</h2>
<p><b>Art. 13.</b> Beneficiarul real al societății este {v(name)}, cu 100% din părțile sociale.
Prezentul act constitutiv a fost redactat în {v("3")} exemplare originale.</p>
<p>Asociat unic și administrator: {v(name)} &nbsp;&nbsp; Semnătura: {v("M. Ionescu")}</p>
"""


def loan_for_use_contract() -> str:
    p, f = PERSON, FIRM
    sediu = f["sediu"].replace("ap. 5", "ap. 6")
    return f"""
<p class="fictiv">{FICTIV}</p>
<h1>CONTRACT DE COMODAT<br>nr. 12 din 01.10.2026</h1>
<h2>I. Părțile</h2>
<p><b>1.1.</b> {v("POP ANDREI")}, CNP {v("1870923120034")}, domiciliat în {v("Cluj-Napoca, str. Horea nr. 30, jud. Cluj")},
identificat cu {v("CI seria CJ nr. 512309")}, în calitate de <b>comodant</b> (proprietar), și</p>
<p><b>1.2.</b> {v(f["nume"] + " (în curs de înmatriculare)")}, reprezentată de {v(p["prenume"] + " " + p["nume"])}, în calitate de
<b>comodatar</b>, au convenit încheierea prezentului contract.</p>
<h2>II. Obiectul contractului</h2>
<p><b>2.1.</b> Comodantul dă în folosință gratuită comodatarului spațiul situat în {v(sediu)},
compus din {v("o cameră de 18 mp")}, proprietatea sa conform extrasului de carte funciară nr. {v("301245")} al municipiului Cluj-Napoca.</p>
<p><b>2.2.</b> Spațiul va fi folosit exclusiv ca <b>sediu social</b> al societății, fără desfășurarea efectivă a activității
(activitatea se desfășoară la beneficiari).</p>
<h2>III. Durata</h2>
<p><b>3.1.</b> Contractul se încheie pe o perioadă de {v("3 ani")}, de la {v("01.10.2026")} până la {v("30.09.2029")}, cu posibilitate de prelungire.</p>
<h2>IV. Obligațiile părților</h2>
<p><b>4.1.</b> Comodantul garantează că spațiul nu face obiectul vreunui litigiu și își dă acordul pentru înregistrarea sediului social la ONRC.</p>
<p><b>4.2.</b> Comodatarul folosește spațiul cu prudență, suportă cheltuielile de folosință și îl restituie la încetarea contractului.</p>
<h2>V. Dispoziții finale</h2>
<p><b>5.1.</b> Folosința este gratuită (art. 2.146 și urm. din Codul civil). Contractul s-a încheiat în 2 exemplare.</p>
<table>
<tr><th>Comodant</th><th>Comodatar</th></tr>
<tr><td>{v("POP ANDREI")}<br>Semnătura: {v("A. Pop")}</td><td>{v(f["nume"])}<br>prin {v(p["prenume"] + " " + p["nume"])}<br>Semnătura: {v("M. Ionescu")}</td></tr>
</table>
"""


INVOICE_ITEMS = [
    ("Laptop Lenovo ThinkPad E16, i7, 32 GB RAM", "buc", 1, 4800.00),
    ("Licență Adobe Creative Cloud — abonament anual", "buc", 1, 2600.00),
    ("Mouse wireless Logitech MX Anywhere", "buc", 1, 180.00),
    ("Masă de protocol cu clientul (catering, 4 persoane)", "serv", 1, 650.00),
    ("Abonament telefonie mobilă + internet, luna octombrie", "luna", 1, 95.00),
]


def expense_invoice() -> str:
    f = FIRM
    rows, base = [], 0.0
    for i, (name, unit, qty, price) in enumerate(INVOICE_ITEMS, 1):
        value = qty * price
        base += value
        rows.append(f"<tr><td>{i}</td><td>{name}</td><td>{unit}</td><td>{qty}</td><td>{price:,.2f}</td>"
                    f"<td>{value:,.2f}</td><td>{value * 0.21:,.2f}</td></tr>")
    vat = base * 0.21
    return f"""
<p class="fictiv">{FICTIV}</p>
<h1>FACTURĂ</h1>
<p>Seria {v("TMD")} nr. {v("004512")} &nbsp;&nbsp; Data emiterii: {v("05.11.2026")} &nbsp;&nbsp; Termen de plată: {v("19.11.2026")}</p>
<table>
<tr><th style="width:50%">Furnizor</th><th>Cumpărător</th></tr>
<tr><td>{v("TECHNO MAGAZIN DEMO SRL")}<br>CUI {v("RO40112233")}, Reg. Com. {v("J12/4410/2019")}<br>
Cluj-Napoca, Calea Florești nr. 58, jud. Cluj<br>IBAN {v("RO55 BTRL 0000 1111 2222 3333")}</td>
<td>{v(f["nume"])}<br>CUI {v(f["cui"])}<br>{v(f["sediu"])}<br>IBAN {v(f["iban"])}</td></tr>
</table>
<br>
<table>
<tr><th>Nr.</th><th>Denumirea produselor / serviciilor</th><th>U.M.</th><th>Cant.</th><th>Preț unitar fără TVA (lei)</th><th>Valoare (lei)</th><th>TVA 21% (lei)</th></tr>
{"".join(rows)}
<tr><td colspan="5"><b>Total</b></td><td><b>{base:,.2f}</b></td><td><b>{vat:,.2f}</b></td></tr>
<tr><td colspan="5"><b>Total de plată (cu TVA)</b></td><td colspan="2"><b>{base + vat:,.2f} lei</b></td></tr>
</table>
<p>Cota TVA: 21%. Plata: ordin de plată. Factura circulă fără semnătură și ștampilă (Codul fiscal, art. 319 alin. (29)).</p>
"""


def main():
    out = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    out.mkdir(parents=True, exist_ok=True)
    render(onrc_request(), out / "FICTIV_cerere_inregistrare_ONRC_Atelier_Verde.pdf")
    render(fiscal_request(), out / "FICTIV_cerere_inregistrare_fiscala_Atelier_Verde.pdf",
           "body { font-size: 8pt; line-height: 1.2; } td, th { font-size: 7.5pt; padding: 1.5pt 3pt; }")
    render(articles_of_association(), out / "FICTIV_act_constitutiv_Atelier_Verde.pdf")
    render(loan_for_use_contract(), out / "FICTIV_contract_comodat_sediu_Atelier_Verde.pdf")
    render(expense_invoice(), out / "FICTIV_factura_cheltuieli_Atelier_Verde.pdf")
    for path in sorted(out.glob("FICTIV_*.pdf")):
        doc = fitz.open(path)
        print(path.name, doc.page_count, "pagini,", sum(len(p.get_text()) for p in doc), "caractere text")


if __name__ == "__main__":
    main()
