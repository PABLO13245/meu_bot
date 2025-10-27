import asyncio
import pytz
from datetime import datetime, timedelta
from analysis import fetch_upcoming_fixtures, analyze_fixtures
import os

# ====================================
# CONFIGURAÇÕES GERAIS
# ====================================
API_TOKEN = os.getenv("SPORTMONKS_API_TOKEN") or "SEU_TOKEN_AQUI"
TZ = pytz.timezone("America/Sao_Paulo")

# ✅ Aqui estão os grupos de ligas (você pode ajustar à vontade)
LEAGUE_GROUPS = [
    "8,564,82,301,271",     # Europa
    "384,501,307",          # América do Sul
    "762,196,847"           # Ásia / Outras
]

# ====================================
# FUNÇÃO PRINCIPAL
# ====================================
async def main():
    print("🟢 Bot iniciado...\n")

    now = datetime.now(TZ)
    start = now
    end = now + timedelta(days=2)  # próximas 48 horas
    start_str = start.strftime("%Y-%m-%d")
    end_str = end.strftime("%Y-%m-%d")

    print(f"📅 Buscando partidas entre {start_str} e {end_str}\n")

    all_fixtures = []

    # 🔁 Loop por grupo de ligas
    for i, league_set in enumerate(LEAGUE_GROUPS):
        print(f"🔎 Grupo {i+1}: {league_set}")

        # ⚽ Agora percorre liga por liga (para evitar erro 400)
        for league_id in league_set.split(','):
            league_id = league_id.strip()
            if not league_id:
                continue

            print(f"   → Buscando liga {league_id}...")
            fixtures = await fetch_upcoming_fixtures(
                API_TOKEN,
                start_str,
                end_str,
                league_ids=league_id
            )

            if fixtures:
                all_fixtures.extend(fixtures)
            else:
                print(f"   ⚠ Nenhuma partida encontrada para liga {league_id}")

    if not all_fixtures:
        print("\n❌ Nenhuma partida encontrada nas próximas 48h.")
        return

    print(f"\n📊 Total de partidas encontradas: {len(all_fixtures)}")
    report = analyze_fixtures(all_fixtures)

    print("\n" + report)

# ====================================
# EXECUÇÃO
# ====================================
if __name__ == "__main__":
    asyncio.run(main())
