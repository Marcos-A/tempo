[Read this in English](README.en.md)

<p align="center">
  <img src="design/brand/svg/lockup/tempo-lockup-pine.svg" alt="Tempo" width="320">
</p>

<p align="center">
  <strong>Planificador curricular compacte per distribuir hores lectives, excloure dies no lectius i exportar la planificació final en XLSX.</strong>
</p>

## Tempo

Tempo és una aplicació petita basada en FastAPI pensada per ajudar centres i professorat a planificar un mòdul al llarg del curs acadèmic amb criteri i sense soroll innecessari. El projecte manté una arquitectura compacta: les regles de negoci viuen principalment a `app/services/`, les rutes HTTP a `app/routes/` i la interfície a `app/templates/`.

## Nota de desenvolupament

Aquest projecte s'ha desenvolupat amb direcció i revisió humanes, amb suport d'eines d'IA per a parts de la implementació, refactorització i documentació del flux de desplegament. Les decisions finals de producte i la responsabilitat sobre el resultat continuen recaient en el responsable del projecte.

## Què permet fer

- definir el calendari lectiu d'un mòdul a partir de dies reals de classe
- excloure períodes no lectius i dates bloquejades des de l'àrea d'administració
- repartir Resultats d'Aprenentatge en seqüència o en blocs paral·lels
- revisar la distribució abans de generar el fitxer final
- exportar la planificació en un llibre XLSX preparat per a revisió manual
- calcular el calendari de pràctiques d'un estudiant (data de fi, dies sense pràctiques i ajustos per dia) i exportar-lo en un XLSX editable que es recalcula sol

## Flux visual

Tempo concentra el flux habitual en dues decisions i un resultat exportable. Les captures següents expliquen aquest recorregut amb el mode seqüencial, que és el cas més habitual.

### 1. Configura el mòdul

Defineix les dates, les hores lectives de cada dia i el nombre de RAs. Des d'aquí també es tria el mode de planificació.

![Formulari inicial per configurar un mòdul en mode seqüencial](docs/screenshots/tempo-step-1-sequencial.png)

### 2. Reparteix les hores disponibles

Tempo calcula les hores lectives reals, descomptant els períodes sense classe, perquè el professorat pugui ordenar els RAs, assignar-los temps i comprovar que no queda cap hora pendent abans de l'exportació.

![Assignació seqüencial d'hores entre resultats d'aprenentatge](docs/screenshots/tempo-step-2-sequencial.png)

### 3. Revisa el llibre exportat

Quan la distribució és completa, l'aplicació genera un llibre XLSX preparat per a la revisió i l'ajust manual.

![Llibre XLSX generat per Tempo](docs/screenshots/tempo-step-3-spreadsheet_1.png)

### Mode per blocs en paral·lel

Quan alguns RAs s'imparteixen simultàniament, es poden dividir les hores setmanals en dos blocs independents i controlar-ne la distribució en minuts.

![Configuració de dos blocs en paral·lel](docs/screenshots/tempo-step-1-parallel.png)

Al segon pas, els RAs es poden repartir, reordenar i validar dins de cada bloc abans de generar el llibre XLSX.

![Assignació de RAs entre blocs en paral·lel](docs/screenshots/tempo-step-2-parallel.png)

La pàgina d'entrada també està disponible a [docs/screenshots/tempo-step-1-landing_page.png](docs/screenshots/tempo-step-1-landing_page.png). Les captures restants, inclosa una segona vista del llibre exportat, es conserven a [docs/screenshots/](docs/screenshots/) per a documentació més detallada.

## Calendari de pràctiques

La secció `/practiques` és independent de la planificació de mòduls i calcula quan acaba el període de pràctiques d'un estudiant.

### A l'aplicació

- **Entrades:** data d'inici, hores totals (amb minuts), hores de cada dia de la setmana i, opcionalment, les dades de l'estudiant i de l'empresa que apareixen a la capçalera del full exportat.
- **Dies sense pràctiques:** els períodes del calendari del centre surten marcats i es poden desmarcar si no afecten l'empresa (p. ex. pràctiques durant les vacances escolars). També s'hi poden afegir altres dies, com festius locals de l'empresa o festius posteriors a les classes.
- **Calendari en directe:** mostra la data de fi, les hores planificades i els dies amb pràctiques. El darrer dia només rep les hores que falten.
- **Ajustos per dia:** en fer clic a qualsevol dia se'n poden canviar les hores, fins i tot posar-hi 0 o afegir-ne en un festiu o cap de setmana. Si es treuen hores, la data de fi s'endarrereix i el calendari afegeix sol els mesos necessaris.
- El formulari es conserva al navegador entre visites.

### Full XLSX exportat

- **Calendari:** una graella per mes, des del mes d'inici fins al mes posterior a la data de fi, perquè es puguin afegir hores més enllà de la data prevista.
- **Hores en format `h:mm`:** cada dia s'escriu com `4:30`; les caselles només accepten valors entre `0:00` i `12:00`, de manera que `4` o `4,5` es rebutgen amb un avís.
- **Totals en format `4h30`:** setmanes, mesos, hores planificades i hores restants es recalculen en editar qualsevol dia, igual que la data de fi.
- **Colors automàtics:** els dies amb hores es mostren en verd i els dies sense pràctiques (`0`, que es mostra com `-`) en vermell. «Hores planificades» i «Hores restants» es marquen en vermell mentre no s'arriba a l'objectiu.
- **Instruccions** a la cantonada superior dreta i **protecció del full** sense contrasenya: només es poden editar les hores dels dies reals i les dades de la capçalera.
- Els fulls **Detall** (un dia per fila amb acumulat i hores restants) i **Configuració** (horari i dies sense pràctiques aplicats) completen el llibre.

## Actius visuals

- `design/brand/` conté els actius mestres de marca i logotip
- `docs/screenshots/` conté les captures optimitzades per a documentació
- [docs/screenshots/README.md](docs/screenshots/README.md) explica el propòsit i manteniment de cada captura

## Stack

- FastAPI
- Jinja templates i JavaScript lleuger
- SQLite
- SQLAlchemy
- openpyxl
- Docker Compose

## Posada en marxa local

El fitxer `docker-compose.yml` està pensat per a desenvolupament local:

- `./app` i `./tests` es munten dins del contenidor
- Uvicorn s'executa amb `--reload`
- la base de dades SQLite es conserva a `./data/app.db`

Passos:

1. Copia `.env.example` a un `.env` propi si vols personalitzar valors.
2. Inicia l'aplicació:

```bash
docker compose up --build
```

3. Obre `http://localhost:8000`
4. El flux de professorat és a `/`
5. L'àrea d'administració és a `/admin`

Si el port `8000` està ocupat:

```bash
HOST_PORT=10080 docker compose up --build
```

## Desplegament tipus producció

Per a una execució sense bind mounts ni `--reload`, fes servir `docker-compose.production.yml`.

```bash
ENV_FILE=/absolute/path/to/.env.prod DATA_DIR=/absolute/path/to/data HOST_PORT=8091 docker compose -f docker-compose.production.yml up -d --build
```

També hi ha l'script del repositori:

```bash
ENV_FILE=/absolute/path/to/.env.prod DATA_DIR=/absolute/path/to/data HOST_PORT=8091 bash scripts/deploy_production.sh
```

Per a una previsualització de branca:

```bash
bash scripts/deploy_preview.sh
```

## Flux de l'aplicació

### Professorat

- `/` mostra el formulari inicial de configuració del mòdul
- `/plan` permet ordenar, repartir i validar els RAs abans d'exportar
- l'exportació final es fa cap a un llibre XLSX
- `/practiques` calcula el calendari de pràctiques a partir de la data d'inici, les hores totals i l'horari setmanal (amb minuts), reutilitza els períodes no lectius configurats, permet ajustar les hores de qualsevol dia i exporta un XLSX editable (vegeu [Calendari de pràctiques](#calendari-de-pràctiques))

### Administració

- `/admin` està protegit per autenticació
- permet gestionar anys acadèmics i dates excloses
- no apareix enllaçat des de la interfície pública

## Variables d'entorn principals

- `APP_NAME`: nom principal visible a la interfície
- `SCHOOL_NAME`: sufix opcional al títol i capçalera
- `SECRET_KEY`: secret de signatura de sessió
- `ADMIN_USERNAME`: usuari d'administració
- `ADMIN_PASSWORD`: contrasenya d'administració
- `DATABASE_URL`: URL de connexió SQLAlchemy
- `WEB_CONCURRENCY`: nombre de processos del servidor en execució tipus producció

## Proves

Per executar la suite principal:

```bash
docker compose run --rm web pytest
```

Per executar les proves focalitzades de serveis:

```bash
pytest tests/test_services.py
```

## Estructura del projecte

```text
app/
  routes/
  services/
  static/
  templates/
design/
  brand/
docs/
  screenshots/
scripts/
tests/
README.md
README.en.md
```

## Recursos de marca i disseny

- `design/tempo-design-system.md`: referència canònica del sistema visual
- `design/brand/README.md`: ús correcte dels logos i variants
- `design/brand/build_svgs.py`: genera tots els SVG del logo a partir dels valors del sistema de disseny (`--check` detecta desviacions)
- `app/static/img/`: subconjunt de logos servits per l'aplicació

## Llicència

Aquest projecte està llicenciat sota `AGPL-3.0-only`. Consulta [LICENSE](LICENSE).
