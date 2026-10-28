extends RefCounted
## Catalog FICTIV de produse (demo). Nu reprezintă oferte sau termeni reali Raiffeisen.

const PRODUCTS := [
	{
		"id": "credit_auto", "category": "credit_auto", "name": "Credit Auto Demo",
		"apr": 0.095, "min_months": 12, "max_months": 84,
		"note": "Dobândă anuală fictivă 9,5%, avans minim 20%.",
	},
	{
		"id": "credit_nevoi", "category": "credit_personal", "name": "Credit de nevoi personale Demo",
		"apr": 0.139, "min_months": 12, "max_months": 60,
		"note": "Dobândă anuală fictivă 13,9%, fără garanții.",
	},
	{
		"id": "plata_rate", "category": "credit_personal", "name": "Plată în rate la comerciant (demo)",
		"apr": 0.0, "min_months": 6, "max_months": 12,
		"note": "Fără dobândă, dar cu comision fictiv de 6% inclus în preț.",
	},
	{
		"id": "card_magazin", "category": "credit_personal", "name": "Card de cumpărături Demo",
		"apr": 0.22, "min_months": 6, "max_months": 36,
		"note": "Dobândă anuală fictivă 22% - cea mai scumpă variantă din catalog.",
	},
	{
		"id": "credit_business", "category": "credit_business", "name": "Credit Micro-Business Demo",
		"apr": 0.099, "min_months": 12, "max_months": 72,
		"note": "Dobândă anuală fictivă 9,9%, pentru echipamente și capital de lucru.",
	},
	{
		"id": "cont_economii", "category": "savings", "name": "Cont de Economii Automat Demo",
		"apr": 0.03, "min_months": 0, "max_months": 0,
		"note": "Dobândă fictivă 3%/an, transfer automat lunar, bani disponibili oricând.",
	},
	{
		"id": "depozit", "category": "savings", "name": "Depozit Flexibil Demo",
		"apr": 0.045, "min_months": 0, "max_months": 0,
		"note": "Dobândă fictivă 4,5%/an, pentru sume care nu sunt necesare imediat.",
	},
	{
		"id": "fond_diversificat", "category": "investment", "name": "Fond Diversificat Demo",
		"apr": 0.07, "min_months": 0, "max_months": 0,
		"note": "Randament mediu estimat 7%/an (fictiv, nu e garantat; poate scădea).",
	},
	{
		"id": "pilon3", "category": "pension", "name": "Pensie Facultativă Demo",
		"apr": 0.06, "min_months": 0, "max_months": 0,
		"note": "Randament mediu estimat 6%/an (fictiv), pe termen lung.",
	},
	{
		"id": "asig_complet", "category": "insurance", "name": "Pachet Protecție Complet Demo",
		"apr": 0.0, "min_months": 0, "max_months": 0,
		"note": "Sănătate + viață + locuință, 280 lei/lună fictivi, acoperă ~85% din costuri medicale.",
	},
	{
		"id": "asig_locuinta", "category": "insurance", "name": "Asigurare Locuință Demo",
		"apr": 0.0, "min_months": 0, "max_months": 0,
		"note": "90 lei/lună fictivi, acoperire limitată (~35%).",
	},
]

static func all() -> Array:
	return PRODUCTS

static func by_id(id: String) -> Dictionary:
	for p: Dictionary in PRODUCTS:
		if str(p.id) == id:
			return p
	return {}

static func by_category(category: String) -> Array:
	var out: Array = []
	for p: Dictionary in PRODUCTS:
		if str(p.category) == category:
			out.append(p)
	return out
