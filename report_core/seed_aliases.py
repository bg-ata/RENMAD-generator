# -*- coding: utf-8 -*-
"""Seed / extend report_core/aliases.json with canonical company names.

Maps the messy variants the CRM + email-domain fallback produce (norm_key =
lowercase alphanumeric) to a clean canonical name. Re-runnable: merges into the
existing file (existing human-added fixes are kept). Run:  python seed_aliases.py
"""
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
PATH = os.path.join(HERE, "aliases.json")


def norm_key(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


# canonical -> list of variant strings (norm_key is applied automatically)
CANON = {
    "Repsol": ["repsol"],
    "Naturgy": ["naturgy", "naturgy renovables", "gas natural"],
    "Engie": ["engie", "engie italia", "engie espana", "engie españa"],
    "EDP": ["edp", "edp renovaveis", "edp renováveis", "edp renewables", "edp renovables", "edp power"],
    "Iberdrola": ["iberdrola"],
    "Endesa": ["endesa"],
    "Enel": ["enel", "enel green power", "egp", "enel x"],
    "Acciona Energía": ["acciona", "acciona energia", "acciona energía", "acicona"],
    "Nordex": ["nordex", "acciona nordex", "acciona nordex green hydrogen"],
    "TotalEnergies": ["totalenergies", "total energies", "total", "totalenergies renewables"],
    "RWE": ["rwe"],
    "BayWa r.e.": ["baywa", "baywa re", "baywa r.e."],
    "Sonnedix": ["sonnedix"],
    "Voltalia": ["voltalia"],
    "Galp": ["galp", "galp energia"],
    "Statkraft": ["statkraft"],
    "Lightsource BP": ["lightsource bp", "lightsourcebp", "lightsource"],
    "Q Energy": ["q energy", "qenergy"],
    "Grenergy": ["grenergy", "grenergy renovables"],
    "OPDEnergy": ["opdenergy", "opd energy"],
    "Zelestra": ["zelestra"],
    "NHOA Energy": ["nhoa", "nhoa energy"],
    "Hitachi Energy": ["hitachi energy", "hitachi"],
    "Huawei": ["huawei"],
    "ABB": ["abb", "it abb"],
    "Siemens Energy": ["siemens energy", "siemens"],
    "Siemens Gamesa": ["siemens gamesa"],
    "Gamesa Electric": ["gamesa electric"],
    "GE Vernova": ["ge vernova", "ge"],
    "Vestas": ["vestas"],
    "Fluence": ["fluence"],
    "Sungrow": ["sungrow"],
    "Trina Solar": ["trina solar", "trinasolar", "trina"],
    "Jinko Solar": ["jinko solar", "jinkosolar", "jinko", "jinko power"],
    "Canadian Solar": ["canadian solar"],
    "JA Solar": ["ja solar"],
    "LONGi": ["longi", "longi solar"],
    "Risen Energy": ["risen energy", "risen"],
    "Hanwha Qcells": ["hanwha", "qcells", "hanwha qcells"],
    "DNV": ["dnv"],
    "Mott MacDonald": ["mott macdonald"],
    "Fichtner": ["fichtner"],
    "Ferrovial": ["ferrovial", "ferrovial energia"],
    "Elecnor": ["elecnor"],
    "EDF": ["edf", "edf renewables"],
    "Shell": ["shell", "shell espana", "shell españa"],
    "BP": ["bp"],
    "Equinor": ["equinor"],
    "Ørsted": ["orsted", "ørsted"],
    "Eni": ["eni", "eni plenitude", "eni plenitude iberia"],
    "Cepsa": ["cepsa", "moeve"],
    "Brookfield": ["brookfield", "brookfield renewable"],
    "Allianz": ["allianz", "allianz global investors"],
    "Mapfre": ["mapfre", "mapfre global risks"],
    "Swiss Re": ["swiss re"],
    "Munich Re": ["munich re"],
    "BBVA": ["bbva"],
    "Abanca": ["abanca"],
    "Santander": ["santander"],
    "KPMG": ["kpmg"],
    "PwC": ["pwc"],
    "Deloitte": ["deloitte"],
    "EY": ["ey", "ernst young"],
    "Alantra": ["alantra", "alantra solar"],
    "Quintas Energy": ["quintas energy"],
    "RP-Global": ["rp global", "rpglobal", "rp global italy"],
    "Nidec": ["nidec"],
    "Wärtsilä": ["wartsila", "wärtsilä"],
    "Octopus Energy": ["octopus energy", "octopus energy generation"],
    "Amazon": ["amazon", "aws"],
    "Veolia": ["veolia"],
    "Kiwa": ["kiwa"],
    "GOPA": ["gopa"],
    "Rolls-Royce": ["rolls royce", "ps rolls royce"],
    "Sinovoltaics": ["sinovoltaics"],
    "One Hub Energy": ["one hub", "one hub energy", "onehub"],
    "ATA Insights": ["ata", "ata insights"],
    "Enerparc": ["enerparc"],
    "Welink": ["welink"],
    "Metlen": ["metlen", "metlen group"],
    "PNE Group": ["pne", "pne group"],
    "BEC Capital": ["bec", "bec capital"],
    "PVcase": ["pvcase"],
    "Vismunda": ["vismunda"],
    "Gotion": ["gotion"],
    "HyperStrong": ["hyperstrong"],
    "Wood": ["wood", "wood plc"],
    "Esparity Solar": ["esparity", "esparity solar"],
    "ABEI Energy": ["abei", "abei energy"],
    "PowerCo": ["powerco"],
    "Jencore": ["jencore"],
    "ID Energy": ["id energy", "idenergy", "id energy group"],
    "Leadernet": ["leadernet"],
    "Zigor": ["zigor"],
    "Plenium Partners": ["plenium", "plenium partners"],
    "Ikigai Energy": ["ikigai", "ikigai energy"],
    "Low Carbon": ["low carbon"],
    "Eurowind Energy": ["eurowind", "eurowind energy"],
    "Fisterra Energy": ["fisterra", "fisterra energy"],
    "FRV": ["frv", "fotowatio", "fotowatio renewable ventures"],
    "Power Capital": ["power capital"],
    "European Energy": ["european energy"],
    "Bureau Veritas": ["bureau veritas"],
    "Enertis Applus": ["enertis", "enertis applus"],
    "Saeta Yield": ["saeta yield", "saeta"],
    "Envision Energy": ["envision", "envision energy"],
    "TTA Energy": ["tta energy"],
    "Creara": ["creara"],
    "Capital Energy": ["capital energy"],
    "Elawan Energy": ["elawan", "elawan energy"],
    "X-Elio": ["x-elio", "xelio", "x-elio energy"],
    "Solarig": ["solarig"],
    "Grupo Cobra": ["cobra"],
    "OHLA": ["ohla", "ohla group"],
    "TSK": ["tsk"],
    "Omexom": ["omexom"],
    "Sterling and Wilson": ["sterling and wilson", "sterling wilson"],
    "ACWA Power": ["acwa power", "acwa"],
    "Masdar": ["masdar"],
    "Iberian Renewables": ["iberica renovables"],
    "Sens": ["sens"],
    "Wincono": ["wincono"],
    "Renovalia": ["renovalia"],
    "Windtec": ["windtec"],
    "EBL": ["ebl"],
    "Aleasoft": ["aleasoft"],
    "Vena Energy": ["vena energy"],
    "TagEnergy": ["tagenergy"],
    "Pine Gate Renewables": ["pine gate renewables", "pine gate"],
    "Recurrent Energy": ["recurrent energy"],
    "EnBW": ["enbw"],
    "Statera Energy": ["statera"],
    "Gore Street Capital": ["gore street", "gore street capital"],
    "Sembcorp": ["sembcorp"],
}


def main():
    aliases = {}
    if os.path.exists(PATH):
        try:
            aliases = json.load(open(PATH, encoding="utf-8"))
        except Exception:
            aliases = {}
    added = 0
    for canon, variants in CANON.items():
        for v in [canon] + variants:
            k = norm_key(v)
            if k and k not in aliases:        # keep existing (human) entries
                aliases[k] = canon
                added += 1
    json.dump(dict(sorted(aliases.items())), open(PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=0)
    print("aliases.json now has %d entries (+%d new)" % (len(aliases), added))


if __name__ == "__main__":
    main()
