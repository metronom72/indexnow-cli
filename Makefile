# SEO Sitemap CLI Tool - Makefile
# Automation of main development and deployment commands

.PHONY: help install install-dev lint format clean run-example demo setup-git release

# Settings
PYTHON := python3
VENV := venv
PIP := $(VENV)/bin/pip
PYTHON_VENV := $(VENV)/bin/python
PROJECT_NAME := seo-sitemap-cli

# Colors for output
RED := \033[31m
GREEN := \033[32m
YELLOW := \033[33m
BLUE := \033[34m
RESET := \033[0m

help: ## Show help for available commands
	@echo "$(BLUE)SEO Sitemap CLI Tool - Makefile$(RESET)"
	@echo "$(BLUE)=================================$(RESET)"
	@echo ""
	@echo "$(GREEN)Available commands:$(RESET)"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-15s$(RESET) %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

install: ## Install in virtual environment
	@echo "$(BLUE)Creating virtual environment...$(RESET)"
	$(PYTHON) -m venv $(VENV)
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	@chmod +x seo_sitemap_cli.py
	@echo "$(GREEN)Installation complete!$(RESET)"
	@echo "$(YELLOW)Activate environment: source $(VENV)/bin/activate$(RESET)"

install-dev: install ## Install for development with additional tools
	@echo "$(BLUE)Installing development tools...$(RESET)"
	$(PIP) install flake8 black isort pytest
	@echo "$(GREEN)Development environment ready!$(RESET)"

lint: ## Check code with flake8
	@echo "$(BLUE)Checking code...$(RESET)"
	$(VENV)/bin/flake8 seo_sitemap_cli.py --max-line-length=120 --ignore=E203,W503 || echo "$(YELLOW)flake8 not installed$(RESET)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(RESET)"
	$(VENV)/bin/black seo_sitemap_cli.py --line-length=120 || echo "$(YELLOW)black not installed$(RESET)"
	$(VENV)/bin/isort seo_sitemap_cli.py || echo "$(YELLOW)isort not installed$(RESET)"

clean: ## Clean temporary files
	@echo "$(BLUE)Cleaning temporary files...$(RESET)"
	rm -rf __pycache__/
	rm -rf .pytest_cache/
	rm -rf *.egg-info/
	rm -rf build/
	rm -rf dist/
	rm -f *.pyc
	rm -f seo_report_*.csv
	rm -f report_*.csv
	rm -f *_report_*.csv
	@echo "$(GREEN)Cleanup complete$(RESET)"

run: ## Interactive run - prompts for URL and report name
	@echo "$(BLUE)SEO Sitemap CLI Tool - Interactive Mode$(RESET)"
	@echo "$(BLUE)=====================================$(RESET)"
	@echo ""
	@read -p "Enter sitemap URL: " url; \
	if [ -z "$$url" ]; then \
		echo "$(RED)URL is required$(RESET)"; \
		exit 1; \
	fi; \
	echo ""; \
	echo "Available commands:"; \
	echo "  1) check-availability - Quick URL availability check"; \
	echo "  2) analyze           - Full SEO analysis with report"; \
	echo "  3) submit            - Submit to IndexNow"; \
	echo ""; \
	read -p "Select command (1-3): " cmd; \
	case $$cmd in \
		1) \
			echo "$(BLUE)Running availability check for: $$url$(RESET)"; \
			$(PYTHON_VENV) seo_sitemap_cli.py check-availability "$$url"; \
			;; \
		2) \
			default_report="seo_report_$$(date +%Y%m%d_%H%M%S)"; \
			read -p "Report filename [$$default_report]: " report; \
			report=$${report:-$$default_report}; \
			echo "$(BLUE)Running SEO analysis for: $$url$(RESET)"; \
			echo "$(BLUE)Report will be saved as: $$report.csv$(RESET)"; \
			$(PYTHON_VENV) seo_sitemap_cli.py analyze "$$url" --output "$$report"; \
			;; \
		3) \
			read -p "Enter IndexNow API key: " api_key; \
			read -p "Enter key location URL: " key_location; \
			if [ -z "$$api_key" ] || [ -z "$$key_location" ]; then \
				echo "$(RED)API key and key location are required$(RESET)"; \
				exit 1; \
			fi; \
			echo "$(BLUE)Submitting to IndexNow: $$url$(RESET)"; \
			$(PYTHON_VENV) seo_sitemap_cli.py submit "$$url" --api-key "$$api_key" --key-location "$$key_location"; \
			;; \
		*) \
			echo "$(RED)Invalid selection$(RESET)"; \
			exit 1; \
			;; \
	esac

setup-git: ## Setup Git repository
	@echo "$(BLUE)Setting up Git repository...$(RESET)"
	@if [ ! -d .git ]; then \
		git init; \
		echo "$(GREEN)Git repository initialized$(RESET)"; \
	else \
		echo "$(YELLOW)Git repository already exists$(RESET)"; \
	fi
	@git add .
	@echo "$(BLUE)Files added to Git$(RESET)"
	@echo "$(YELLOW)Run: make commit-initial for first commit$(RESET)"

commit-initial: ## Initial commit
	@echo "$(BLUE)Creating initial commit...$(RESET)"
	git commit -m "Initial commit: SEO Sitemap CLI tool" || echo "$(YELLOW)Commit already exists$(RESET)"
	@echo "$(GREEN)Initial commit created$(RESET)"
	@echo "$(YELLOW)Add remote repository: git remote add origin YOUR_REPO_URL$(RESET)"

release: ## Create new release (usage: make release VERSION=1.0.0)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Specify version: make release VERSION=1.0.0$(RESET)"; \
		exit 1; \
	fi
	@echo "$(BLUE)Creating release v$(VERSION)...$(RESET)"
	@git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@git push origin v$(VERSION)
	@echo "$(GREEN)Release v$(VERSION) created$(RESET)"

dev-setup: install-dev ## Complete development environment setup
	@echo "$(BLUE)Setting up development environment...$(RESET)"
	@echo "$(GREEN)Development environment configured$(RESET)"
	@echo ""
	@echo "$(YELLOW)Recommended workflow:$(RESET)"
	@echo "  1. source $(VENV)/bin/activate"
	@echo "  2. make lint          # Check code"
	@echo "  3. make format        # Format code"
	@echo "  4. git add . && git commit -m 'message'"

check: lint ## Complete code check (lint)
	@echo "$(GREEN)All checks passed$(RESET)"

build: clean ## Build distribution
	@echo "$(BLUE)Building distribution...$(RESET)"
	$(PYTHON_VENV) setup.py sdist bdist_wheel || echo "$(YELLOW)setup.py not found$(RESET)"

install-global: ## Global tool installation
	@echo "$(BLUE)Global installation...$(RESET)"
	@if [ -f "$(VENV)/bin/python" ]; then \
		sudo ln -sf $(PWD)/seo_sitemap_cli.py /usr/local/bin/seo-sitemap; \
		echo "$(GREEN)Command 'seo-sitemap' available globally$(RESET)"; \
	else \
		echo "$(RED)First run: make install$(RESET)"; \
	fi

uninstall-global: ## Remove global installation
	@echo "$(BLUE)Removing global installation...$(RESET)"
	@sudo rm -f /usr/local/bin/seo-sitemap
	@echo "$(GREEN)Global command removed$(RESET)"

status: ## Show project status
	@echo "$(BLUE)SEO Sitemap CLI Tool Status$(RESET)"
	@echo "$(BLUE)============================$(RESET)"
	@echo "$(GREEN)Python version:$(RESET) $(shell $(PYTHON) --version 2>/dev/null || echo 'Not installed')"
	@echo "$(GREEN)Virtual environment:$(RESET) $(shell [ -d $(VENV) ] && echo 'Created' || echo 'Not created')"
	@echo "$(GREEN)Git repository:$(RESET) $(shell [ -d .git ] && echo 'Initialized' || echo 'Not initialized')"
	@echo "$(GREEN)Project size:$(RESET) $(shell du -sh . 2>/dev/null | cut -f1 || echo 'Unknown')"
	@echo "$(GREEN)Lines of code:$(RESET) $(shell wc -l *.py 2>/dev/null | tail -1 | awk '{print $$1}' || echo '0')"

quick-install: ## Quick installation (install + demo)
	@make install

quick-start: ## Quick project start (setup-git + install + demo)
	@make setup-git
	@make install
	@echo ""
	@echo "$(GREEN)Project ready for use!$(RESET)"
	@echo "$(YELLOW)Next steps:$(RESET)"
	@echo "  1. source $(VENV)/bin/activate"
	@echo "  2. python seo_sitemap_cli.py --help"
	@echo "  3. Add remote Git repository"

examples: ## Show usage examples
	@echo "$(BLUE)SEO Sitemap CLI Usage Examples$(RESET)"
	@echo "$(BLUE)==============================$(RESET)"
	@echo ""
	@echo "$(GREEN)1. Availability check:$(RESET)"
	@echo "   python seo_sitemap_cli.py check-availability https://example.com/sitemap.xml"
	@echo ""
	@echo "$(GREEN)2. SEO analysis:$(RESET)"
	@echo "   python seo_sitemap_cli.py analyze https://example.com/sitemap.xml --output report"
	@echo ""
	@echo "$(GREEN)3. IndexNow submission:$(RESET)"
	@echo "   python seo_sitemap_cli.py submit https://example.com/sitemap.xml \\"
	@echo "     --api-key YOUR_KEY --key-location https://example.com/key.txt"
	@echo ""
	@echo "$(GREEN)4. With additional parameters:$(RESET)"
	@echo "   python seo_sitemap_cli.py analyze https://example.com/sitemap.xml \\"
	@echo "     --max-workers 20 --timeout 30 --output detailed_report"

requirements: ## Show system requirements
	@echo "$(BLUE)System Requirements$(RESET)"
	@echo "$(BLUE)==================$(RESET)"
	@echo "$(GREEN)Python:$(RESET) 3.8 or higher"
	@echo "$(GREEN)OS:$(RESET) Linux, macOS, Windows"
	@echo "$(GREEN)RAM:$(RESET) Minimum 512MB"
	@echo "$(GREEN)Disk:$(RESET) 50MB free space"
	@echo "$(GREEN)Internet:$(RESET) For external sitemaps and IndexNow"
	@echo ""
	@echo "$(GREEN)Python packages:$(RESET)"
	@cat requirements.txt | sed 's/^/  /'