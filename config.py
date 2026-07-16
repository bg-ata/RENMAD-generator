"""Brand configuration for RENMAD content generator — v2026.1"""

# ── Brand constants (from Manual de Identidad Corporativa 2026) ───────────────
BRAND = {
    "red":       "#B52030",   # Rojo Carmesí — color principal de marca
    "black":     "#111111",   # Fondos, texto
    "white":     "#FFFFFF",
    "gray_soft": "#F2F2F0",   # Fondos secundarios
    "gray_mid":  "#888888",
    "ata_orange":"#F03C00",   # ATA Insights
}

THEMES = {
    # ── Orange-red events ─────────────────────────────────────────────────────
    "almacenamiento": {
        "name": "Almacenamiento",
        "label_es": "Almacenamiento Energético",
        "label_en": "Energy Storage",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_almacenamiento.png",
        "bg_folder": "almacenamiento",
    },
    "storage_italia": {
        "name": "Storage Italia",
        "label_es": "Storage Italia",
        "label_en": "Storage Italia",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_storage_italia.png",
        "bg_folder": "almacenamiento",   # shares photo bank with Almacenamiento
    },
    "storage_polska": {
        "name": "Storage Polska",
        "label_es": "Storage Polska",
        "label_en": "Storage Polska",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_storage_polska.png",
        "bg_folder": "almacenamiento",   # shares photo bank with Almacenamiento
    },
    "mexico": {
        "name": "México",
        "label_es": "Energías Renovables México",
        "label_en": "Renewable Energy Mexico",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_mexico.png",
        "bg_folder": "mexico",
    },
    "invest": {
        "name": "Invest",
        "label_es": "Inversión Renovable",
        "label_en": "Renewable Investment",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_invest.png",
        "bg_folder": "invest",
    },
    "invest_italia": {
        "name": "Invest Italia",
        "label_es": "Invest Italia",
        "label_en": "Invest Italia",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_invest_italia.png",
        "bg_folder": "invest",   # shares photo bank with Invest
    },
    "chile": {
        "name": "Chile",
        "label_es": "Energías Renovables Chile",
        "label_en": "Renewable Energy Chile",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_chile.png",
        "bg_folder": "chile",
    },
    # ── Blue events ───────────────────────────────────────────────────────────
    "datacenters": {
        "name": "Datacenters",
        "label_es": "Datacenters",
        "label_en": "Datacenters",
        "hex": "#29ACE3",
        "rgb": (41, 172, 227),
        "logo_filename": "logo_datacenters.png",
        "bg_folder": "datacenters",
    },
    "datacenters_italia": {
        "name": "Datacenters Italia",
        "label_es": "Datacenters Italia",
        "label_en": "Datacenters Italia",
        "hex": "#29ACE3",
        "rgb": (41, 172, 227),
        "logo_filename": "logo_datacenters_italia.png",
        "bg_folder": "datacenters",   # shares photo bank with Datacenters
    },
    # ── Green events ──────────────────────────────────────────────────────────
    "hidrogeno": {
        "name": "Hidrógeno",
        "label_es": "Hidrógeno Verde",
        "label_en": "Green Hydrogen",
        "hex": "#3E8C28",
        "rgb": (62, 140, 40),
        "logo_filename": "logo_hidrogeno.png",
        "bg_folder": "hidrogeno",
    },
    # ── Purple events ─────────────────────────────────────────────────────────
    "biometano": {
        "name": "Biometano",
        "label_es": "Gas Renovable / Biometano",
        "label_en": "Renewable Gas / Biomethane",
        "hex": "#5C3285",
        "rgb": (92, 50, 133),
        "logo_filename": "logo_biometano.png",
        "bg_folder": "biometano",
    },
    # ── ATA Insights (sees ALL background banks) ──────────────────────────────
    "ata_insights": {
        "name": "ATA Insights",
        "label_es": "ATA Insights",
        "label_en": "ATA Insights",
        "hex": "#E84830",
        "rgb": (232, 72, 48),
        "logo_filename": "logo_ata_insights.png",
        "bg_folder": "__all__",   # special: aggregates every theme folder
    },
}

COLOURS = {
    "white": "#FFFFFF",
    "off_white": "#F5F5F5",
    "dark_grey": "#333333",
    "mid_grey": "#666666",
    "light_grey": "#CCCCCC",
    "black": "#000000",
}

FONTS = {
    "header":    "Montserrat",   # Black / Bold for headlines
    "body":      "Inter",        # Regular / SemiBold for body text
}

LANGUAGE_STRINGS = {
    "es": {
        "cta_label": "Regístrate gratis hoy",
        "moderator": "Moderador/a",
        "moderator_m": "Moderador",
        "moderator_f": "Moderadora",
        "welcome": "Bienvenidos",
        "break": "Descanso",
        "lunch": "Comida",
        "end_of_day": "Fin del día",
        "mute_phone": "Silencia tu teléfono",
        "wifi_password": "Contraseña WiFi",
        "free_webinar": "WEBINAR GRATUITO",
        "starting_soon": "Empezamos pronto",
        "recording_available": "Grabación disponible",
        "date_label": "FECHA",
        "time_label": "HORA",
        "hosted_by": "HOSTED BY:",
        # Ingo (LinkedIn share)
        "ingo_speaker_cta":  "ÚNETE A MI INTERVENCIÓN",
        "ingo_attendee_cta": "NOS VEMOS EN",
        "ingo_host_label":   "HOST",
        "ingo_online":       "Online",
        "weekdays":          ["Lunes", "Martes", "Miércoles", "Jueves",
                              "Viernes", "Sábado", "Domingo"],
        "months":            ["enero", "febrero", "marzo", "abril", "mayo", "junio",
                              "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"],
        "months_short":      ["ENE", "FEB", "MAR", "ABR", "MAY", "JUN",
                              "JUL", "AGO", "SEP", "OCT", "NOV", "DIC"],
        # Event Marketing Pack
        "event_cta":         "¡Obtén tu pase ahora!",
    },
    "en": {
        "cta_label": "Register for free today",
        "moderator": "Moderator",
        "moderator_m": "Moderator",
        "moderator_f": "Moderator",
        "welcome": "Welcome",
        "break": "Break",
        "lunch": "Lunch",
        "end_of_day": "End of day",
        "mute_phone": "Mute your phone",
        "wifi_password": "WiFi password",
        "free_webinar": "FREE WEBINAR",
        "starting_soon": "Starting soon",
        "recording_available": "Recording available",
        "date_label": "DATE",
        "time_label": "TIME",
        "hosted_by": "HOSTED BY:",
        # Ingo (LinkedIn share)
        "ingo_speaker_cta":  "JOIN MY SESSION",
        "ingo_attendee_cta": "SEE YOU AT",
        "ingo_host_label":   "HOST",
        "ingo_online":       "Online",
        "weekdays":          ["Monday", "Tuesday", "Wednesday", "Thursday",
                              "Friday", "Saturday", "Sunday"],
        "months":            ["january", "february", "march", "april", "may", "june",
                              "july", "august", "september", "october", "november", "december"],
        "months_short":      ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"],
        # Event Marketing Pack
        "event_cta":         "Get your pass today!",
    },
    "it": {
        "cta_label": "Registrati gratuitamente oggi",
        "moderator": "Moderatore/trice",
        "moderator_m": "Moderatore",
        "moderator_f": "Moderatrice",
        "welcome": "Benvenuti",
        "break": "Pausa",
        "lunch": "Pranzo",
        "end_of_day": "Fine giornata",
        "mute_phone": "Silenzia il telefono",
        "wifi_password": "Password WiFi",
        "free_webinar": "WEBINAR GRATUITO",
        "starting_soon": "Iniziamo a breve",
        "recording_available": "Registrazione disponibile",
        "date_label": "DATA",
        "time_label": "ORA",
        "hosted_by": "HOSTED BY:",
        # Ingo (LinkedIn share)
        "ingo_speaker_cta":  "PARTECIPA AL MIO INTERVENTO",
        "ingo_attendee_cta": "CI VEDIAMO A",
        "ingo_host_label":   "HOST",
        "ingo_online":       "Online",
        "weekdays":          ["Lunedì", "Martedì", "Mercoledì", "Giovedì",
                              "Venerdì", "Sabato", "Domenica"],
        "months":            ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
                              "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"],
        "months_short":      ["GEN", "FEB", "MAR", "APR", "MAG", "GIU",
                              "LUG", "AGO", "SET", "OTT", "NOV", "DIC"],
        # Event Marketing Pack
        "event_cta":         "Acquista subito il tuo pass!",
    },
    "pl": {
        "cta_label": "Zarejestruj się bezpłatnie",
        "moderator": "Moderator/ka",
        "moderator_m": "Moderator",
        "moderator_f": "Moderatorka",
        "welcome": "Witamy",
        "break": "Przerwa",
        "lunch": "Obiad",
        "end_of_day": "Koniec dnia",
        "mute_phone": "Wycisz telefon",
        "wifi_password": "Hasło WiFi",
        "free_webinar": "BEZPŁATNY WEBINAR",
        "starting_soon": "Zaczynamy wkrótce",
        "recording_available": "Nagranie dostępne",
        "date_label": "DATA",
        "time_label": "GODZINA",
        "hosted_by": "HOSTED BY:",
        # Ingo (LinkedIn share)
        "ingo_speaker_cta":  "DOŁĄCZ DO MOJEJ SESJI",
        "ingo_attendee_cta": "DO ZOBACZENIA NA",
        "ingo_host_label":   "HOST",
        "ingo_online":       "Online",
        "weekdays":          ["Poniedziałek", "Wtorek", "Środa", "Czwartek",
                              "Piątek", "Sobota", "Niedziela"],
        "months":            ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
                              "lipca", "sierpnia", "września", "października", "listopada", "grudnia"],
        "months_short":      ["STY", "LUT", "MAR", "KWI", "MAJ", "CZE",
                              "LIP", "SIE", "WRZ", "PAŹ", "LIS", "GRU"],
        # Event Marketing Pack
        "event_cta":         "Zdobądź swój bilet już dziś!",
    },
}

OUTPUT_TYPES = {
    "slide":    {"name": "Slide",      "size": (1920, 1080), "format": "pptx+png"},
    "deck":     {"name": "Slide Deck", "size": (1920, 1080), "format": "pptx+png"},
    "linkedin": {"name": "LinkedIn",   "size": (1200, 630),  "format": "png"},
    "myata":    {"name": "My ATA",     "size": (1280, 720),  "format": "pptx+png"},
    "ingo":     {"name": "Ingo",       "size": (1200, 630),  "format": "png"},
}
