extends RefCounted
## Cele 10 decizii din viața lui Ana (22 -> 52 de ani). Toate datele sunt fictive.
## `location`: home | bank | work | shop | advisor
## `compare` (opțional): scenariu de credit pentru compare_products()

const Sim := preload("res://scripts/raiff/finance_sim.gd")

const LOCATION_NAMES := {
	"home": "Acasă", "bank": "Banca", "work": "Serviciu", "shop": "Magazin", "advisor": "Consilier",
}

static func all() -> Array:
	return [
		{
			"id": "buget", "age": 22, "location": "home", "title": "Primul tău buget",
			"scene": "Ai primul salariu stabil: 4.300 lei net pe lună. Chiria și facturile consumă aproape tot, iar în cont ai doar 1.200 lei puși deoparte pentru urgențe. Cum îți organizezi banii?",
			"category": "savings",
			"lesson": "Un transfer automat la începutul lunii bate promisiunea de a economisi „ce rămâne”.",
			"options": [
				{"title": "Plătește-te primul", "desc": "Transfer automat de 400 lei/lună (tot surplusul) în fondul de urgență, până la 6 luni de cheltuieli.",
					"ops": {"emergency_contrib": 400.0, "mood": {"stress": -2.0, "conf": 6.0}}},
				{"title": "Economisesc ce rămâne", "desc": "Fără transfer automat. Banii „rămași” se pierd în cheltuieli mici (+250 lei/lună).",
					"ops": {"living_add": 250.0, "mood": {"conf": 0.0}}},
				{"title": "Împart: fond de urgență + investiție", "desc": "250 lei/lună în fondul de urgență și 150 lei/lună într-un fond diversificat.",
					"ops": {"emergency_contrib": 250.0, "invest_contrib": 150.0, "mood": {"conf": 4.0}}},
			],
		},
		{
			"id": "job", "age": 25, "location": "work", "title": "Oferta de la serviciu",
			"scene": "După 3 ani ai rezultate bune. Managerul îți propune un rol nou, iar un recruiter îți oferă un job la altă firmă, cu program mai lung.",
			"category": "",
			"lesson": "Venitul este cea mai puternică pârghie financiară la început de carieră, dar costă timp și energie.",
			"options": [
				{"title": "Negociez o mărire aici", "desc": "Rămâi în echipă și ceri +12% salariu. Risc mic, câștig moderat.",
					"ops": {"salary_mult": 1.12, "mood": {"conf": 4.0}}},
				{"title": "Schimb jobul (+35%)", "desc": "Salariu mult mai mare, dar naveta și programul adaugă 200 lei/lună cheltuieli și mai mult stres.",
					"ops": {"salary_mult": 1.35, "living_add": 200.0, "mood": {"stress": 10.0, "conf": 4.0}}},
				{"title": "Curs de specializare + negociere", "desc": "Investești 2.400 lei într-un curs și ceri +22% după certificare.",
					"ops": {"spend": 2400.0, "salary_mult": 1.22, "mood": {"conf": 8.0}}},
			],
		},
		{
			"id": "auto", "age": 28, "location": "bank", "title": "Prima mașină",
			"scene": "Ai nevoie de mașină pentru navetă. O mașină mai nouă costă 40.000 lei, iar banca (fictivă) îți propune un credit auto. Cât de lung să fie creditul?",
			"category": "credit_auto",
			"compare": {"product": "credit_auto", "amount": 30000.0, "months": [60, 36]},
			"lesson": "Rata mică de pe 60 de luni înseamnă mai multă dobândă plătită în total. Rata mare de pe 36 de luni strânge bugetul.",
			"options": [
				{"title": "Credit auto pe 60 de luni", "desc": "Avans 10.000 lei, credit 30.000 lei la 9,5%. Rată mai mică, dobândă totală mai mare.",
					"ops": {"spend": 10000.0, "loan": {"name": "Credit auto", "principal": 30000.0, "apr": 0.095, "months": 60}, "car_value": 40000.0, "living_add": 450.0, "mood": {"stress": 4.0}}},
				{"title": "Credit auto pe 36 de luni", "desc": "Avans 10.000 lei, credit 30.000 lei la 8,9%. Rată mare, dar plătești mult mai puțină dobândă.",
					"ops": {"spend": 10000.0, "loan": {"name": "Credit auto", "principal": 30000.0, "apr": 0.089, "months": 36}, "car_value": 40000.0, "living_add": 450.0, "mood": {"stress": 6.0}}},
				{"title": "Mașină second-hand", "desc": "Mașină de 22.000 lei: avans 8.000 lei și credit de 14.000 lei pe 36 de luni la 10,5%.",
					"ops": {"spend": 8000.0, "loan": {"name": "Credit second-hand", "principal": 14000.0, "apr": 0.105, "months": 36}, "car_value": 22000.0, "living_add": 380.0, "mood": {"stress": 2.0}}},
				{"title": "Fără mașină", "desc": "Transport în comun și car-sharing: +250 lei/lună, iar naveta de 2 ore te obosește. Zero credit.",
					"ops": {"living_add": 250.0, "mood": {"stress": 10.0, "conf": -2.0}}},
			],
		},
		{
			"id": "avarie", "age": 31, "location": "home", "title": "Avarie neprevăzută",
			"scene": "Se strică instalația din casă: reparația costă 9.500 lei și nu poate aștepta. Ce faci?",
			"category": "credit_personal",
			"compare": {"product": "credit_nevoi", "amount": 9500.0, "months": [24, 12]},
			"lesson": "Un fond de urgență transformă o criză în incident. Fără el, plătești dobândă la ghinion.",
			"options": [
				{"title": "Plătesc din economii", "desc": "Folosești numerarul și fondul de urgență. Fără dobândă, dar îți golești plasa de siguranță.",
					"ops": {"spend": 9500.0, "mood": {"stress": 4.0}}},
				{"title": "Credit de nevoi personale", "desc": "9.500 lei pe 24 de luni la 13,9%. Păstrezi economiile, plătești dobândă.",
					"ops": {"loan": {"name": "Credit nevoi personale", "principal": 9500.0, "apr": 0.139, "months": 24}, "mood": {"stress": 6.0}}},
				{"title": "Plată în 12 rate la magazin", "desc": "Fără dobândă, dar cu comision de 6% inclus: 10.070 lei în 12 rate.",
					"ops": {"loan": {"name": "Rate instalator", "principal": 10070.0, "apr": 0.0, "months": 12}, "mood": {"stress": 5.0}}},
				{"title": "Amân reparația", "desc": "Problema se agravează: peste 6 luni costă 13.000 lei, iar între timp stai cu grija.",
					"ops": {"spend": 13000.0, "mood": {"stress": 16.0, "conf": -6.0}}},
			],
		},
		{
			"id": "blackfriday", "age": 34, "location": "shop", "title": "Ofertă de Black Friday",
			"scene": "Home cinema, laptop nou și o vacanță, toate la reducere: 7.000 lei. Casierul îți oferă „24 de rate ușoare” pe cardul magazinului.",
			"category": "credit_personal",
			"compare": {"product": "card_magazin", "amount": 7000.0, "months": [24, 12]},
			"lesson": "Un card de magazin cu dobândă mare poate anula orice reducere.",
			"options": [
				{"title": "Cumpăr doar ce planificasem", "desc": "1.500 lei, plătiți imediat. Restul ofertei rămâne în raft.",
					"ops": {"spend": 1500.0, "mood": {"conf": 2.0}}},
				{"title": "Cumpăr tot, din banii mei", "desc": "7.000 lei plătiți acum. Te bucuri de ele, dar economiile scad.",
					"ops": {"spend": 7000.0, "mood": {"stress": -5.0, "conf": 2.0}}},
				{"title": "Cumpăr tot în rate", "desc": "7.000 lei pe 24 de luni la cardul magazinului (22% dobândă).",
					"ops": {"loan": {"name": "Card magazin", "principal": 7000.0, "apr": 0.22, "months": 24}, "mood": {"stress": -2.0, "conf": 1.0}}},
			],
		},
		{
			"id": "asigurari", "age": 37, "location": "advisor", "title": "Asigurări: ai plasă de siguranță?",
			"scene": "Consilierul observă că nu ai nicio asigurare în afară de cele obligatorii. Îți prezintă un pachet fictiv și o variantă simplă pentru locuință.",
			"category": "insurance",
			"lesson": "Asigurarea nu aduce randament, dar protejează tot ce ai construit atunci când apare un eveniment mare.",
			"options": [
				{"title": "Pachet complet de protecție", "desc": "280 lei/lună. Acoperă aproximativ 85% dintr-o urgență medicală.",
					"ops": {"insurance_level": 2, "insurance_premium": 280.0, "mood": {"stress": -6.0, "conf": 4.0}}},
				{"title": "Doar asigurare pentru locuință", "desc": "90 lei/lună. Acoperire medicală limitată (aproximativ 35%).",
					"ops": {"insurance_level": 1, "insurance_premium": 90.0, "mood": {"stress": -2.0}}},
				{"title": "Fără asigurări", "desc": "Economisești acum 280 lei/lună și accepți riscul unui eveniment mare.",
					"ops": {"mood": {"conf": 0.0}}},
			],
		},
		{
			"id": "bonus", "age": 40, "location": "work", "title": "Bonusul anual",
			"scene": "Primești un bonus net de 18.000 lei. Ai idei multe: datorii de închis, o investiție, o renovare. Ce prioritizezi?",
			"category": "investment",
			"lesson": "Ordinea contează: întâi dobânzile mari și plasa de siguranță, apoi investițiile și plăcerile.",
			"options": [
				{"title": "Rambursez datoriile", "desc": "Plătești anticipat descoperitul și creditele cu dobânda cea mai mare. Restul merge în economii.",
					"ops": {"bonus": {"amount": 18000.0, "mode": "prepay"}, "mood": {"stress": -4.0, "conf": 4.0}}},
				{"title": "Investesc totul în fond", "desc": "18.000 lei într-un fond diversificat. Randament mai mare, dar cu risc de scădere.",
					"ops": {"bonus": {"amount": 18000.0, "mode": "fund"}, "mood": {"conf": 3.0}}},
				{"title": "Fond de urgență + depozit", "desc": "Completezi fondul de urgență, iar restul intră într-un depozit flexibil.",
					"ops": {"bonus": {"amount": 18000.0, "mode": "safe"}, "mood": {"stress": -3.0, "conf": 2.0}}},
				{"title": "Renovare și vacanță", "desc": "12.000 lei pe bucurii acum, 6.000 lei în economii.",
					"ops": {"bonus": {"amount": 18000.0, "mode": "spend", "spend": 12000.0}, "mood": {"stress": -6.0, "conf": 2.0}}},
			],
		},
		{
			"id": "medical", "age": 43, "location": "home", "title": "Urgență medicală în familie",
			"scene": "Un părinte are nevoie urgentă de tratament. Varianta privată costă 16.000 lei, varianta publică cu recuperare costă 7.000 lei. Ce alegi?",
			"category": "insurance",
			"lesson": "Decizia de acum 6 ani, când ai ales asigurarea, își arată efectul chiar acum.",
			"options": [
				{"title": "Clinică privată, imediat", "desc": "16.000 lei din care asigurarea (dacă o ai) acoperă o parte. Tratament rapid, stres mic.",
					"ops": {"medical_cost": 16000.0, "mood": {"stress": 3.0}}},
				{"title": "Spital public + recuperare", "desc": "7.000 lei, cu așteptare și drumuri. Costă mai puțin, dar obosește.",
					"ops": {"medical_cost": 7000.0, "mood": {"stress": 14.0, "conf": -4.0}}},
				{"title": "Clinică privată, plată în rate", "desc": "16.000 lei în 12 rate fără dobândă. Păstrezi lichiditățile.",
					"ops": {"medical_cost": 16000.0, "finance_months": 12, "mood": {"stress": 5.0}}},
			],
		},
		{
			"id": "afacere", "age": 46, "location": "bank", "title": "Extinderea micii afaceri",
			"scene": "Proiectul tău paralel de consultanță merge bine. Cu 25.000 lei poți cumpăra echipament și angaja un colaborator part-time. Cum finanțezi extinderea?",
			"category": "credit_business",
			"compare": {"product": "credit_business", "amount": 25000.0, "months": [60, 36]},
			"lesson": "Un credit de business e sănătos doar dacă veniturile noi acoperă rata chiar și într-un an slab.",
			"options": [
				{"title": "Credit micro-business, 60 luni", "desc": "25.000 lei la 9,9%. Venit suplimentar estimat de ~1.700 lei/lună, plus datorie și presiune.",
					"ops": {"loan": {"name": "Credit micro-business", "principal": 25000.0, "apr": 0.099, "months": 60}, "business_value": 20000.0, "side_income_add": 1700.0, "mood": {"stress": 10.0, "conf": 6.0}}},
				{"title": "Extind treptat din economii", "desc": "Investești 8.000 lei numerar. Venit suplimentar de ~600 lei/lună, fără datorii.",
					"ops": {"spend": 8000.0, "business_value": 7000.0, "side_income_add": 600.0, "mood": {"stress": 3.0, "conf": 3.0}}},
				{"title": "Caut un partener", "desc": "Împarți profitul: aproximativ +500 lei/lună, fără bani investiți de tine.",
					"ops": {"side_income_add": 500.0, "mood": {"stress": 2.0, "conf": 2.0}}},
				{"title": "Rămân așa", "desc": "Nu schimbi nimic. Stabilitate și mai mult timp liber.",
					"ops": {"mood": {"stress": -2.0}}},
			],
		},
		{
			"id": "pensie", "age": 49, "location": "advisor", "title": "Pregătește pensia",
			"scene": "Ultima mare decizie: pensia este peste 18 ani. Cât investești lunar pentru viitorul tău?",
			"category": "pension",
			"lesson": "Timpul lucrează pentru tine: fiecare an de contribuții în plus înseamnă mai mult decât o sumă mare la final.",
			"options": [
				{"title": "600 lei/lună în pensie facultativă", "desc": "Contribuție fixă și automată. Efort moderat.",
					"ops": {"invest_contrib": 600.0, "mood": {"conf": 6.0}}},
				{"title": "1.200 lei/lună", "desc": "Dublezi efortul. Mai puțină libertate acum, mult mai mult capital la 67 de ani.",
					"ops": {"invest_contrib": 1200.0, "mood": {"stress": 4.0, "conf": 8.0}}},
				{"title": "Nu schimb nimic", "desc": "Continui ca până acum și te bazezi pe pensia de stat.",
					"ops": {"mood": {"conf": -2.0}}},
			],
		},
	]

## Adaptează prima decizie (bugetul) la cifrele reale din extrasul de cont al jucătorului.
static func personalize(events: Array, s: Dictionary) -> Array:
	var out := events.duplicate(true)
	var budget: Dictionary = out[0]
	var surplus := Sim.monthly_surplus(s)
	var contrib := maxf(snappedf(surplus, 50.0), 100.0)
	var to_emergency := maxf(snappedf(contrib * 0.6, 50.0), 50.0)
	var to_fund := maxf(contrib - to_emergency, 50.0)
	var situation := "Îți rămân aproximativ %s pe lună." % Sim.money(surplus) if surplus > 0.5 else "Cheltuielile și ratele depășesc venitul cu %s pe lună." % Sim.money(-surplus)
	budget.scene = "Din extrasul tău de cont: venit net %s/lună, cheltuieli %s, rate %s. %s În cont ai %s. Cum îți organizezi banii de acum înainte?" % [
		Sim.money(Sim.income(s)), Sim.money(float(s.living)), Sim.money(Sim.debt_payments(s)), situation, Sim.money(float(s.cash))]
	budget.options[0].desc = "Transfer automat de %s/lună în fondul de urgență, până la 6 luni de cheltuieli." % Sim.money(contrib)
	budget.options[0].ops.emergency_contrib = contrib
	budget.options[2].desc = "%s/lună în fondul de urgență și %s/lună într-un fond diversificat." % [Sim.money(to_emergency), Sim.money(to_fund)]
	budget.options[2].ops.emergency_contrib = to_emergency
	budget.options[2].ops.invest_contrib = to_fund
	return out
