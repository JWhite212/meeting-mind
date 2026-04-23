# MeetingMind — Build & Install Automation
#
# Targets:
#   make setup       — Create venv, install Python and UI dependencies
#   make build       — Build daemon binary, copy resources, build Tauri app
#   make install     — Build everything, then install the launch agent
#   make dev         — Start the Tauri dev server with hot-reload
#   make test        — Run the Python test suite
#   make lint        — Run ruff linter on src/ and tests/
#   make clean       — Remove all build artefacts
#   make clean-all   — Deep clean (also removes venv, node_modules, Rust cache)
#   make size        — Show disk usage breakdown by component

.PHONY: setup build-daemon copy-daemon build-app build install dev test lint clean clean-all size

setup:
	@echo "==> Creating virtual environment (if missing)"
	test -d .venv || python3 -m venv .venv
	@echo "==> Installing Python dependencies"
	.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
	@echo "==> Installing UI dependencies"
	cd ui && npm install

build-daemon:
	./scripts/build_daemon.sh

copy-daemon:
	@echo "==> Copying daemon to Tauri resources"
	mkdir -p ui/src-tauri/resources/meetingmind-daemon
	cp -R dist/meetingmind-daemon/ ui/src-tauri/resources/meetingmind-daemon/

build-app:
	cd ui && npm run tauri build

build: build-daemon copy-daemon build-app

install: build
	./scripts/install.sh

dev:
	cd ui && npm run tauri dev

test:
	source .venv/bin/activate && python3 -m pytest tests/ -v

lint:
	source .venv/bin/activate && ruff check src/ tests/

clean:
	@echo "==> Cleaning build artefacts"
	rm -rf dist/
	rm -rf build/
	rm -rf ui/dist/
	rm -rf ui/src-tauri/resources/meetingmind-daemon/
	rm -rf ui/src-tauri/target/release/bundle/

clean-all: clean
	@echo "==> Deep clean (venv, node_modules, Rust cache)"
	rm -rf .venv/
	rm -rf ui/node_modules/
	rm -rf ui/src-tauri/target/

size:
	@echo "==> Project disk usage"
	@du -sh . 2>/dev/null || true
	@echo ""
	@echo "--- Breakdown ---"
	@du -sh .venv/ 2>/dev/null            || echo "  .venv/                  (not present)"
	@du -sh ui/node_modules/ 2>/dev/null   || echo "  ui/node_modules/        (not present)"
	@du -sh ui/src-tauri/target/ 2>/dev/null || echo "  ui/src-tauri/target/    (not present)"
	@du -sh dist/ 2>/dev/null              || echo "  dist/                   (not present)"
	@du -sh build/ 2>/dev/null             || echo "  build/                  (not present)"
	@du -sh ui/src-tauri/resources/meetingmind-daemon/ 2>/dev/null || echo "  ui/.../meetingmind-daemon/ (not present)"
