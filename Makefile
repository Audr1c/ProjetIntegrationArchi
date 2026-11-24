# ==========================================================
#  Projet CNN CIFAR-10 sur SoC — Python → virgule fixe → HLS → FPGA
#  `make` seul affiche la liste des commandes.
#  Pour documenter une nouvelle cible : `cible: deps ## description`
#
#  Arborescence imposée (vérifiée par `make tree-check`, qui ignore les
#  périphériques /dev/null montés par le sandbox de Claude Code) :
#    python/   référence algorithmique (.py uniquement)
#    cpp/      modèle C++ virgule fixe + testbench
#    hls/      sources et scripts Catapult (hls/include : ac_fixed.h, ac_int.h)
#    fpga/     projet Vivado : scripts .tcl, contraintes .xdc, VHDL
#    data/     CIFAR-10 (ignoré par git) et data/coef/ (coefficients versionnés)
#    doc/      sujets et documentation
#    rapport/  rapport final
#    build/    sorties générées (ignoré par git)
# ==========================================================

PYTHON  ?= python3
VENV    := .venv
PY      := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip

SRC_DIR := python
SRCS    := $(wildcard $(SRC_DIR)/*.py)

# --- Arborescence ---
DIRS      := python cpp hls hls/include fpga data data/coef doc rapport build Results Exploration
# Seuls ces éléments sont autorisés à la racine du dépôt
ROOT_OK   := $(DIRS) Makefile README.md CLAUDE.md AGENTS.md requirements.txt \
             .gitignore .gitattributes .git .venv .claude .vscode
# Fichiers indispensables
REQUIRED  := data/cifar-10-batches-bin/data_batch_1.bin \
             data/coef/CNN_coeff_3x3.txt \
             hls/include/ac_fixed.h

.DEFAULT_GOAL := help
.PHONY: help init tree tree-check venv check run explore validate efficiency coeffs nonreg tb-hls clean distclean

help: ## Affiche cette aide
	@echo "Commandes disponibles :"
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  \033[36mmake %-11s\033[0m %s\n", $$1, $$2}' "$(firstword $(MAKEFILE_LIST))"

# ---------------- Arborescence ----------------

init: ## Crée les dossiers manquants (avec .gitkeep)
	@for d in $(DIRS); do \
	  if [ ! -d "$$d" ]; then mkdir -p "$$d" && echo "  créé : $$d/"; fi; \
	  if [ -z "$$(ls -A "$$d")" ]; then touch "$$d/.gitkeep"; fi; \
	done
	@echo "Arborescence OK."

tree: ## Affiche l'arborescence du projet
	@find . -path ./.git -prune -o -path ./$(VENV) -prune -o -path ./.claude -prune \
	  -o -path ./data/cifar-10-batches-bin -prune -o -name __pycache__ -prune -o -name .claude -prune \
	  -o -print | sed -e 's|^\./||' -e '/^\.$$/d' | sort | \
	  awk -F/ '{ printf "%*s%s%s\n", 2*(NF-1), "", $$NF, "" }'

tree-check: ## Vérifie que l'arborescence est respectée
	@err=0; \
	for d in $(DIRS); do \
	  [ -d "$$d" ] || { echo "✗ dossier manquant : $$d/  (lancer make init)"; err=1; }; \
	done; \
	for f in * .[!.]*; do \
	  [ -e "$$f" ] || continue; \
	  [ -c "$$f" ] && continue; \
	  case " $(ROOT_OK) " in *" $$f "*) ;; \
	    *) echo "✗ hors arborescence à la racine : $$f"; err=1;; esac; \
	done; \
	for f in $(SRC_DIR)/*; do \
	  case "$$f" in *.py|*/__pycache__|*/.gitkeep) ;; \
	    *) echo "✗ $$f : seuls des .py vont dans $(SRC_DIR)/ (données -> data/)"; err=1;; esac; \
	done; \
	for f in $(REQUIRED); do \
	  [ -e "$$f" ] || echo "⚠ fichier attendu absent : $$f"; \
	done; \
	if [ $$err -ne 0 ]; then echo "Arborescence non conforme."; exit 1; fi; \
	echo "Arborescence conforme."

# ---------------- Python ----------------

# Le fichier témoin est refait seulement si requirements.txt change
$(VENV)/.installed: requirements.txt
	$(PYTHON) -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	touch $@

venv: $(VENV)/.installed ## Crée le venv et installe requirements.txt

check: tree-check venv ## Vérifie l'arborescence et compile les .py
	$(PY) -m py_compile $(SRCS)
	@echo "Compilation OK : $(SRCS)"

run: check ## Lance python/main.py (crée le venv si besoin)
	cd $(SRC_DIR) && "$(CURDIR)/$(PY)" main.py

explore: venv ## Exploration bits/précision (ARGS="run --runs 3", "list", "plot"…)
	"$(CURDIR)/$(PY)" Exploration/explore.py $(or $(ARGS),--help)

validate: venv ## Teste des configs sur plus d'images (ARGS="<run> <run>:ref float -b test 2")
	"$(CURDIR)/$(PY)" Exploration/validate.py $(or $(ARGS),--help)

efficiency: venv ## Efficacité des pas des runs passés (bits gagnés × poids / précision perdue)
	MPLCONFIGDIR="$${MPLCONFIGDIR:-$${TMPDIR:-/tmp}}" "$(CURDIR)/$(PY)" Exploration/efficiency.py $(ARGS)

# ---------------- HLS (hls/AUDIT_HLS.md) ----------------

coeffs: venv ## Regénère les ROM cpp/coeffs_k3.hpp et coeffs_k5.hpp depuis data/coef/
	"$(CURDIR)/$(PY)" hls/gen_coeffs.py

nonreg: ## Non-régression bit-exacte : scores de 200 images (k=5) vs hls/ref/scores_k5.txt
	@cmake -S cpp -B cpp/build >/dev/null && cmake --build cpp/build -j >/dev/null
	@mkdir -p build
	@cpp/build/main 200 5 data_batch_1.bin --dump build/scores_k5.txt >/dev/null
	@if cmp -s build/scores_k5.txt hls/ref/scores_k5.txt; then \
	    echo "OK : scores identiques à hls/ref/scores_k5.txt (200 images)"; \
	elif [ "$$(head -1 build/scores_k5.txt)" != "$$(head -1 hls/ref/scores_k5.txt)" ]; then \
	    echo "Formats de cpp/config.hpp différents de ceux de la référence : comparaison impossible"; \
	    echo "  (nouvelle référence : cpp/build/main 200 5 data_batch_1.bin --dump hls/ref/scores_k5.txt)"; exit 1; \
	else \
	    echo "ÉCHEC : scores différents de hls/ref/scores_k5.txt"; \
	    diff build/scores_k5.txt hls/ref/scores_k5.txt | head -6; exit 1; \
	fi

tb-hls: ## Testbench HLS sans Catapult (ARGS=nb_images, défaut 3)
	@cmake -S cpp -B cpp/build >/dev/null && cmake --build cpp/build -j >/dev/null
	cpp/build/tb_hls $(ARGS)

clean: ## Supprime les caches et build/
	rm -rf $(SRC_DIR)/__pycache__ build/*

distclean: clean ## Supprime aussi le venv
	rm -rf $(VENV)
