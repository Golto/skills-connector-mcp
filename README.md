# mcp-skills-connector

Serveur MCP exposant une bibliothèque de *skills* (instructions, scripts,
ressources annexes) consultables et exécutables par n'importe quel agent
connecté. Une skill regroupe une documentation (`SKILL.md`) et,
éventuellement, des fichiers annexes sans structure imposée (scripts,
templates, références).

Le serveur distingue deux catégories de skills :

- **`base/`** : skills écrites à la main, immuables par l'agent.
- **`generated/`** : skills créées dynamiquement par l'agent en composant
  des skills existantes.

## Sommaire

- [Prérequis](#prérequis)
- [Installation](#installation)
- [Arborescence des données](#arborescence-des-données)
- [Profils](#profils)
- [Lancement du serveur](#lancement-du-serveur)
- [Outils MCP exposés](#outils-mcp-exposés)
- [Ressource `skills://index`](#ressource-skillsindex)
- [Structure d'une skill](#structure-dune-skill)
- [Exécution sandboxée](#exécution-sandboxée)
- [Architecture du code](#architecture-du-code)

## Prérequis

- Python ≥ 3.13
- [uv](https://docs.astral.sh/uv/)
- Docker (uniquement si un profil active `allow_execution`)

## Installation

```bash
git clone <repo-url> skills-connector-mcp
cd skills-connector-mcp
uv sync
```

Aucune étape supplémentaire n'est nécessaire : le serveur crée sa structure
de données au premier lancement (voir [Arborescence des données](#arborescence-des-données)).

## Arborescence des données

Le serveur lit et écrit dans un dossier fixe, indépendant du répertoire du
projet :

```
~/.config/scripts/mcp-skills/
├── registry.json
├── base/
│   └── <skill_id>/
│       ├── SKILL.md           # toujours présent, racine de la skill
│       └── ...                 # structure libre : docs, scripts, templates
├── generated/
│   └── <skill_id>/
│       ├── SKILL.md
│       ├── manifest.json
│       └── ...
├── profiles/
│   ├── <profile_id>.json
│   └── default.json           # créé automatiquement si absent
└── workspaces/
    └── <profile_id>/          # workspace par défaut d'un profil (voir Workspace)
```

### Bootstrap

Au démarrage, avant toute autre opération, chaque élément manquant de cette
arborescence est créé indépendamment des autres (`base/`, `generated/`,
`profiles/`, `registry.json`, `profiles/default.json`). Un fichier existant,
même partiellement corrompu, n'est jamais touché : une erreur explicite est
levée et le démarrage est interrompu.

### Resynchronisation du registry

Après le bootstrap et avant le chargement du profil, `registry.json` est
reconcilié avec l'état réel de `base/` et `generated/` sur le disque :

- skill présente sur disque mais absente du registry → ajout automatique ;
- skill présente dans le registry mais absente du disque → suppression de
  l'entrée ;
- hash différent (contenu de `SKILL.md` + fichiers annexes) → mise à jour de
  l'entrée.

Cette synchronisation est silencieuse : les diffs détectées sont corrigées
sans erreur. Seul un `registry.json` invalide (JSON malformé) lève une
erreur explicite.

## Profils

Un profil définit le scope de skills visibles pour une instance du serveur
et les capacités autorisées :

```json
{
  "name": "dev",
  "description": "Profil de développement",
  "allow_generation": true,
  "allow_execution": false,
  "skill_ids": ["python-style", "git-workflow"]
}
```

| Champ | Description |
|---|---|
| `skill_ids` | Liste exhaustive des skills visibles (mélange `base`/`generated` possible) |
| `allow_generation` | Active `create_skill` et `set_profile_skills` |
| `allow_execution` | Active `run_bash_command` |

Le scope (liste d'ids + flags) est résolu **une seule fois** au démarrage et
reste fixe pour toute la durée de vie du process. Une skill créée par une
instance n'est pas visible par une autre instance déjà lancée avec le même
profil, tant que celle-ci n'a pas redémarré.

## Lancement du serveur

Le profil actif est résolu dans cet ordre de précédence :

1. argument CLI `--profile <id>` ;
2. variable d'environnement `MCP_SKILLS_PROFILE` ;
3. profil `default`.

```bash
MCP_SKILLS_PROFILE=dev uv run mcp run main.py
```

Pour le développement, l'inspecteur MCP. `uv run mcp dev main.py` ne
convient pas ici : l'inspecteur relance le serveur dans un sous-processus
sans lui transmettre les variables d'environnement (seulement `PATH`,
`HOME`, etc.), si bien que le profil `default` serait chargé en silence.
Lancer l'inspecteur directement, en lui passant les variables avec `-e` :

```bash
npx @modelcontextprotocol/inspector -e MCP_SKILLS_PROFILE=dev uv run mcp run main.py
```

Au démarrage, le serveur écrit sur stderr le profil et le workspace
réellement chargés, ce qui permet de vérifier la configuration d'un coup
d'œil (panneau de notifications de l'inspecteur).

Si `MCP_SKILLS_PROFILE` pointe vers un profil inexistant, une erreur
explicite est écrite sur stderr avant d'être relevée (l'inspecteur MCP
avalant silencieusement les exceptions d'import, `main.py` intercepte les
erreurs de démarrage pour garantir leur visibilité dans le terminal).

### Workspace

Le workspace est l'ensemble des dossiers de l'hôte visibles sous
`/workspace` dans la sandbox et dans les outils de fichiers. Il est fixé au
lancement, comme le profil, selon cet ordre de précédence (pour chaque
option, l'argument CLI l'emporte sur sa variable d'environnement) :

1. `--paths-dir <dossier>` / `MCP_SKILLS_PATHS_DIR` : un dossier contenant
   un `paths.json` qui associe des noms à des dossiers de l'hôte. Chaque
   entrée est montée sous `/workspace/<nom>`. C'est le même flag, avec le
   même sens, que pour `mcp-project-navigator` et `mcp-project-writer` : un
   client comme agent-worker leur passe la même valeur, et le fichier vu
   comme projet `memory`, chemin `notes.md` par ces serveurs est
   `/workspace/memory/notes.md` dans la sandbox. Les chemins relatifs du
   `paths.json` sont résolus depuis le dossier qui le contient.
2. `--workspace <dossier>` / `MCP_SKILLS_WORKSPACE` : un seul dossier, monté
   comme `/workspace`.
3. Sinon, `~/.config/scripts/mcp-skills/workspaces/<profile_id>/`, créé à
   la demande.

Les dossiers fournis explicitement ne sont jamais créés : un dossier absent
(ou un `paths.json` invalide) interrompt le démarrage avec une erreur
explicite (`WorkspaceConfigError`).

```json
{
  "memory": "/chemin/vers/agents/default/workplace/memory",
  "artefacts": "/chemin/vers/agents/default/workplace/artefacts"
}
```

### Configuration Claude Desktop

```json
{
  "mcpServers": {
    "SkillsConnector": {
      "command": "uv",
      "env": {
        "MCP_SKILLS_PROFILE": "default"
      },
      "args": [
        "--directory",
        "/chemin/absolu/vers/skills-connector-mcp",
        "run",
        "mcp",
        "run",
        "main.py"
      ]
    }
  }
}
```

## Outils MCP exposés

Un outil non autorisé par le profil n'est **pas enregistré** sur le serveur
(absence pure dans le manifeste MCP), pas un refus applicatif à l'appel.

Les arguments de chaque outil sont **plats** (`{"skill_id": "..."}`) et non
encapsulés dans un objet `request` : cette imbrication était une source
fréquente d'appels d'outils malformés avec les petits modèles locaux. Chaque
paramètre porte sa description et ses contraintes dans le schéma JSON de
l'outil.

### Toujours chargés

| Outil | Description |
|---|---|
| `list_skills` | Liste les skills du scope courant (id, description, tags, origin, has_resources) |
| `search_skills` | Recherche par mots-clés parmi id/description/triggers/tags, sémantique ET, `limit` optionnel |
| `read_skill` | Retourne le contenu de `SKILL.md` |
| `list_files` | Liste récursivement un dossier de la sandbox (`/` par défaut), en chemins absolus |
| `read_file` | Lit un fichier texte de la sandbox par tranches de lignes (`start_line`, `next_start_line`) |

### Chargés si `allow_execution = true`

| Outil | Description |
|---|---|
| `run_bash_command` | Exécute une commande shell dans un conteneur Docker jetable, hors réseau |
| `write_file` | Écrit un fichier texte sous `/workspace`. **Absent avec `--paths-dir`** : le client dispose alors déjà d'un writer sur les mêmes dossiers, et deux outils d'écriture concurrents égarent les petits modèles |

Tous les outils de fichiers partagent le vocabulaire de chemins de la
sandbox (voir [Exécution sandboxée](#exécution-sandboxée)) : un chemin
renvoyé par l'un s'utilise tel quel dans les autres et dans une commande.

### Chargés si `allow_generation = true`

Non implémentés pour le moment. `create_skill` et `set_profile_skills` sont
prévus par la spécification mais n'ont pas encore de code associé : le
branchement conditionnel existe déjà dans `server.py` (commenté), en
attente de leur implémentation.

## Ressource `skills://index`

En plus des outils, le serveur expose une ressource MCP `skills://index`
(`text/markdown`) : un index compact des skills du scope courant, une ligne
par skill (id, description, triggers, marqueur `[files]` si la skill a des
fichiers annexes), précédé de consignes d'usage.

Elle est destinée à être **injectée dans le prompt système** de l'agent par
le client MCP. Le modèle sait ainsi d'emblée quelles skills existent, sans
devoir penser à appeler `list_skills` : il ne lit le `SKILL.md` complet via
`read_skill` que lorsqu'une tâche s'y rapporte (divulgation progressive).

Les consignes ne mentionnent que les outils réellement enregistrés pour le
profil actif. La phrase sur `list_files` / `read_file` n'apparaît que si au
moins une skill a des fichiers annexes. Si `allow_execution` est actif, une
section `## Sandbox` décrit le layout réel de ce process : `/skills`, puis
soit `/workspace` seul, soit chaque dossier nommé du `paths.json` relié à
son nom de projet, avec la consigne d'utiliser `write_file` quand il est
enregistré. C'est le seul endroit où le layout est détaillé, plutôt que dans
chaque réponse d'outil.

```markdown
# Available skills

Skills are packaged instructions for specific kinds of tasks. [...]

- golto-python-style: Conventions de style Python. Use when: écrire du code Python.
- fiche-recap-math: Génère une fiche récap de maths. [files]

## Sandbox

run_bash_command runs shell commands in a fresh container, without network: [...]
- /skills/<skill_id>/: skill files, read-only. [...]
- /workspace/memory/: read-write, kept between calls. Same files as the project 'memory' [...]
- /workspace/artefacts/: [...]
/workspace/ is the working directory but is itself read-only: [...]
```

## Structure d'une skill

En dehors de `SKILL.md` (toujours à la racine) et de `manifest.json`
(uniquement pour `generated/`), aucune structure interne n'est imposée :
une skill peut contenir un `reference.md`, un dossier `scripts/`, un dossier
`templates/`, ou toute autre organisation. Conséquence directe : aucun
outil ne présuppose de sous-dossier conventionnel, d'où `list_files` pour
découvrir l'arborescence réelle (`/skills/<skill_id>/`) avant de cibler une
lecture avec `read_file`.

### `SKILL.md`

Les métadonnées (`description`, `triggers`, `tags`) sont extraites d'un bloc
frontmatter YAML en tête de fichier :

```markdown
---
description: Conventions de style Python pour ce projet
triggers:
  - écrire du code Python
  - style Python
tags:
  - python
  - style
---

# Contenu de la skill...
```

### `manifest.json` (skills générées)

```json
{
  "composed_from": ["python-style", "git-workflow"],
  "created_at": "2026-06-29T10:00:00+00:00"
}
```

## Exécution sandboxée

### Vocabulaire de chemins

L'agent ne manipule jamais de chemin de l'hôte. Tous les outils (fichiers
et commandes) parlent le même langage :

| Chemin | Contenu | Accès |
|---|---|---|
| `/skills/<skill_id>/` | chaque skill du scope | lecture seule |
| `/workspace/` ou `/workspace/<nom>/` | le workspace (voir [Workspace](#workspace)) | lecture/écriture |

Un chemin relatif part de `/workspace`. `/`, `/skills` et un `/workspace`
découpé en dossiers nommés sont des répertoires virtuels : on peut les
lister, pas y écrire. La résolution vers l'hôte (`sandbox_paths.py`) passe
par la même liste de montages que celle qui démarre le conteneur
(`sandbox_mounts.py`), et refuse tout chemin, lien symbolique compris, qui
sortirait de son montage.

Comme le workspace est fait de dossiers de l'hôte, ce qu'une commande y
écrit survit au conteneur, sans identifiant à transporter d'un appel à
l'autre, et reste visible des autres outils travaillant sur ces dossiers.

### `run_bash_command`

`run_bash_command(command, timeout_seconds=30)` exécute `bash -c <command>`
dans un conteneur Docker jetable (`docker run --rm`), depuis `/workspace` :

- **Image** : image unique et fixe (`mcp-skills-runner:latest` par défaut),
  jamais choisie par l'agent. Construite automatiquement au démarrage du
  serveur si le profil actif a `allow_execution = true` et que l'image
  n'existe pas encore localement ou que le Dockerfile a changé. Dockerfile
  bundlé sous `docker/mcp-skills-runner/Dockerfile` (base
  `python:3.13-slim` + `git`, `curl`, `jq`, `requests`, `pyyaml`, `sympy`).
- **Montages** : toutes les skills du scope sous `/skills` (lecture seule),
  le workspace sous `/workspace` (lecture/écriture), via `--mount` (qui
  échoue si la source manque, là où `-v` la créerait en root).
- **Isolation** : pas de réseau (`--network none`), utilisateur de l'hôte
  (`--user uid:gid`, les fichiers écrits appartiennent à l'utilisateur qui
  lance le serveur), système de
  fichiers racine en lecture seule avec un `/tmp` en mémoire, aucune
  capability, `no-new-privileges`. `HOME=/tmp`.
- **Limites** (variables d'environnement, jamais exposées à l'agent) :

  | Variable | Défaut | Rôle |
  |---|---|---|
  | `MCP_SKILLS_DOCKER_IMAGE` | `mcp-skills-runner:latest` | image |
  | `MCP_SKILLS_DOCKER_MEMORY` | `512m` | mémoire, et mémoire + swap |
  | `MCP_SKILLS_DOCKER_CPUS` | `1.0` | CPU |
  | `MCP_SKILLS_DOCKER_PIDS` | `256` | nombre de processus |
  | `MCP_SKILLS_DOCKER_TMP_SIZE` | `256m` | taille de `/tmp` |
  | `MCP_SKILLS_OUTPUT_LIMIT_BYTES` | `8000` | octets gardés par flux (stdout, stderr) |
  | `MCP_SKILLS_SNAPSHOT_MAX_FILES` | `20000` | fichiers suivis pour `changed_files` |

- **Timeout** : `timeout_seconds` (défaut 30, maximum 600). Un dépassement
  tue le conteneur (`docker kill`) et retourne le code `124` ; les fichiers
  déjà écrits sont conservés.
- **Non bloquant** : la commande tourne dans un sous-processus asynchrone,
  le serveur continue de répondre pendant ce temps.

La réponse :

```json
{
  "exit_code": 0,
  "stdout": "...",
  "stderr": "",
  "is_output_truncated": false,
  "changed_files": ["/workspace/artefacts/plot.png"],
  "deleted_files": []
}
```

- Une sortie trop longue garde son début et sa fin, avec un marqueur
  `[... N bytes truncated ...]` au milieu. Elle est lue au fil de l'eau :
  la mémoire de l'hôte reste bornée quoi que la commande affiche.
- `changed_files` / `deleted_files` comparent taille et mtime de chaque
  fichier du workspace avant et après la commande, et listent au plus 50
  chemins (puis `"... and N more"`). Au-delà de
  `MCP_SKILLS_SNAPSHOT_MAX_FILES` fichiers, ils valent `null`. Une écriture
  faite par un autre processus pendant la commande y apparaît aussi.

### Convention pour les scripts de skills

Un script de skill est lancé par son chemin complet
(`python /skills/<skill_id>/scripts/cli.py ...`), sans `cd` dans son
dossier, et doit se contenter des dépendances de l'image (pas de réseau,
donc pas de `pip install`). Il lit et écrit dans `/workspace` ; ses imports
internes doivent être relatifs à son propre fichier, pas au dossier
courant.

## Architecture du code

```
src/
├── storage/                        # couche persistance, indépendante du protocole MCP
│   ├── exceptions.py               # exceptions métier (SkillNotFoundError, PathEscapeError, ...)
│   ├── models.py                   # Pydantic (SkillEntry, Registry, Profile, Manifest) + ServerScope (dataclass)
│   ├── paths.py                    # résolution des chemins absolus sous ~/.config/scripts/mcp-skills
│   ├── hashing.py                  # SHA256 sur SKILL.md + fichiers annexes triés
│   ├── bootstrap.py                # création idempotente de la structure de données
│   ├── registry_store.py           # lecture/écriture atomique + resynchronisation du registry
│   ├── profile_store.py            # lecture/écriture des profils
│   ├── skill_store.py              # lecture SKILL.md, garde-fou path traversal, création de skills
│   ├── workspace.py                # résolution du workspace : paths.json, dossier unique ou défaut
│   └── file_access.py              # listing, lecture par lignes, écriture atomique sur l'hôte
└── mcp/
    ├── context.py                   # AppRequestContext (scope + registry + workspace) injecté dans chaque outil
    ├── launch_options.py            # resolve_launch_options() : profil, --paths-dir, --workspace
    ├── server.py                    # build_server(): bootstrap, sync, enregistrement des outils
    ├── prompts/                     # vide pour le moment
    ├── resources/
    │   └── skills_index/
    │       └── resource.py          # build_skills_index() : index Markdown + section Sandbox
    └── tools/
        ├── shared_models.py         # SkillSummary, SkillIdParameter, SandboxPathParameter
        ├── scope_guard.py           # require_skill_in_scope() pour read_skill
        ├── sandbox_mounts.py        # build_sandbox_mounts() : /skills + /workspace, source unique des montages
        ├── sandbox_paths.py         # resolve_sandbox_path() : chemin sandbox vers chemin hôte
        ├── list_skills/
        ├── search_skills/
        ├── read_skill/
        ├── list_files/
        ├── read_file/
        ├── write_file/              # + is_write_file_available()
        └── run_bash_command/
            ├── models.py            # RunBashCommandRequest/Response
            ├── tool.py              # orchestration : relevés du workspace, exécution, réponse
            ├── config.py            # image/limites/timeouts, surchargeables par variables d'environnement
            ├── docker_runner.py     # docker run asynchrone durci, timeout + kill
            ├── output_capture.py    # BoundedOutputBuffer : début + fin de chaque flux
            ├── workspace_changes.py # relevés taille/mtime, changed_files / deleted_files
            └── image_builder.py     # ensure_runner_image_available() : inspect puis build si absente
```

Chaque outil MCP suit la même convention : `tools/<nom_outil>/models.py`
(Pydantic request/response, plus les alias `Annotated` de ses paramètres) et
`tools/<nom_outil>/tool.py` (`execute_<nom_outil>(request, ctx) -> Response`).
Les fonctions outils sont enregistrées dans `server.py` via des wrappers
`@mcp.tool()` fins, à arguments plats, qui reconstruisent le modèle de
requête puis délèguent immédiatement à la fonction `execute_*`
correspondante. Les alias `Annotated` (par exemple `SkillIdParameter`) sont
partagés entre les modèles de requête et les signatures des wrappers : la
description et les contraintes d'un paramètre ne sont écrites qu'une fois.
Cette séparation permet de tester la logique métier indépendamment du
décodage FastMCP.

### `main.py` / `server.py`

`uv run mcp dev main.py` importe le module à la recherche d'une variable
globale `FastMCP` : il n'appelle jamais de fonction `main()` et ne transmet
aucun flag CLI au module. `main.py` expose donc directement
`mcp = build_server(resolve_launch_options())` au niveau module, tandis que
`launch_options.py` résout les options de lancement et `server.py` contient
toute la logique de construction (`build_server`).