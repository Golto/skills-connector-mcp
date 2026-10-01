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
└── scratch/
    └── <scratch_id>/          # workspaces de run_bash_command
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

Pour le développement, l'inspecteur MCP :

```bash
MCP_SKILLS_PROFILE=dev uv run mcp dev main.py
```

Si `MCP_SKILLS_PROFILE` pointe vers un profil inexistant, une erreur
explicite est écrite sur stderr avant d'être relevée (l'inspecteur MCP
avalant silencieusement les exceptions d'import, `main.py` intercepte les
erreurs de démarrage pour garantir leur visibilité dans le terminal).

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
| `list_skill_files` | Retourne l'arborescence complète de la skill (`manifest.json` exclu) |
| `read_skill_resource` | Retourne le contenu d'un fichier précis, identifié par chemin relatif |

### Chargés si `allow_execution = true`

| Outil | Description |
|---|---|
| `run_bash_command` | Exécute une commande shell dans un conteneur Docker jetable, scopé à une skill |

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
profil actif : la phrase sur `run_bash_command` n'apparaît que si
`allow_execution` est actif, celle sur `list_skill_files` /
`read_skill_resource` que si au moins une skill a des fichiers annexes.

```markdown
# Available skills

Skills are packaged instructions for specific kinds of tasks. [...]

- golto-python-style: Conventions de style Python. Use when: écrire du code Python.
- fiche-recap-math: Génère une fiche récap de maths. [files]
```

## Structure d'une skill

En dehors de `SKILL.md` (toujours à la racine) et de `manifest.json`
(uniquement pour `generated/`), aucune structure interne n'est imposée :
une skill peut contenir un `reference.md`, un dossier `scripts/`, un dossier
`templates/`, ou toute autre organisation. Conséquence directe : aucun
outil ne présuppose de sous-dossier conventionnel, d'où la présence de
`list_skill_files` pour découvrir l'arborescence réelle avant de cibler une
lecture avec `read_skill_resource`.

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

`run_bash_command` exécute une commande dans un conteneur Docker jetable :

- **Image** : image unique et fixe (`mcp-skills-runner:latest` par défaut),
  jamais choisie par l'agent. Construite automatiquement au démarrage du
  serveur si le profil actif a `allow_execution = true` et que l'image
  n'existe pas encore localement (`docker image inspect` puis `docker build`
  si absente). Dockerfile bundlé sous `docker/mcp-skills-runner/Dockerfile`
  (base `python:3.13-slim` + `git`, `curl`, `jq`, `requests`, `pyyaml`).
- **Montages** :
  - dossier racine de la skill monté en **lecture seule** sous `/skill` ;
  - dossier scratch dédié monté en **lecture/écriture** sous `/workspace`,
    qui est aussi le répertoire de travail du conteneur.
- **Réseau** : désactivé (`--network none`), non paramétrable.
- **Limites** : mémoire et CPU fixées au niveau serveur (variables
  d'environnement `MCP_SKILLS_DOCKER_MEMORY` / `MCP_SKILLS_DOCKER_CPUS`,
  non exposées à l'agent), timeout configurable par appel
  (`timeout_seconds`, défaut 30s). Un dépassement de timeout tue le
  conteneur (`docker kill`) et retourne le code de sortie `124`.

### Réutilisation de workspace (`scratch_id`)

Chaque appel accepte un `scratch_id` optionnel. Omis, un nouvel identifiant
est généré et un dossier scratch vide est créé. Fourni (récupéré depuis la
réponse d'un appel précédent), le même dossier `/workspace` est réutilisé,
ce qui permet à l'agent d'itérer sur les mêmes fichiers à travers plusieurs
appels sans repartir de zéro. L'identifiant est validé par expression
régulière (`[a-zA-Z0-9_-]+`) pour écarter toute tentative de traversal.

```json
{
  "skill_id": "git-workflow",
  "command": "git clone https://example.com/repo.git .",
  "scratch_id": null
}
```

La réponse retourne toujours un `scratch_id`, même lorsqu'il a été généré
automatiquement, à repasser dans un appel suivant :

```json
{
  "stdout": "...",
  "stderr": "",
  "exit_code": 0,
  "output_files": ["README.md"],
  "workspace_path": "/home/.../scratch/a1b2c3d4",
  "scratch_id": "a1b2c3d4"
}
```

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
│   ├── skill_store.py              # lecture SKILL.md/ressources, garde-fou path traversal, création de skills
│   └── scratch.py                   # résolution/génération des dossiers scratch pour run_bash_command
└── mcp/
    ├── context.py                   # AppRequestContext (scope + registry + workspace) injecté dans chaque outil
    ├── launch_options.py            # resolve_launch_options() : profil, --paths-dir, --workspace
    ├── server.py                    # build_server(): bootstrap, sync, enregistrement des outils
    ├── prompts/                     # vide pour le moment
    ├── resources/
    │   └── skills_index/
    │       └── resource.py          # build_skills_index() : index Markdown du scope pour le prompt système
    └── tools/
        ├── shared_models.py         # SkillSummary + SkillIdParameter partagés entre outils
        ├── scope_guard.py           # require_skill_in_scope() partagé entre les outils prenant un skill_id
        ├── list_skills/
        ├── search_skills/
        ├── read_skill/
        ├── list_skill_files/
        ├── read_skill_resource/
        └── run_bash_command/
            ├── models.py            # RunBashCommandRequest/Response
            ├── tool.py              # orchestration : scope guard, résolution scratch, appel Docker
            ├── config.py            # image/limites/timeouts, surchargeables par variables d'environnement
            ├── docker_runner.py     # subprocess docker run, gestion timeout + kill
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