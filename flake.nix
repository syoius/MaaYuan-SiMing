{
  description = "Python 3.10 dev shell with pip, venv, and auto requirements.txt install (cached)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.05";
  };

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" "x86_64-darwin" "aarch64-darwin" ];
      forAllSystems = f:
        nixpkgs.lib.genAttrs systems (system:
          f (import nixpkgs {
            inherit system;
            config.allowUnfree = true;
          })
        );
    in {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = with pkgs; [
            python310
            python310Packages.pip
            python310Packages.virtualenv
          ];

          shellHook = ''
            echo "🐍 Python 3.10 development shell starting..."

            # 创建 .venv （若不存在）
            if [ ! -d .venv ]; then
              python -m venv .venv
              echo "✅ Created virtual environment (.venv)"
            fi

            # 激活虚拟环境
            # shellcheck disable=SC1091
            source .venv/bin/activate
            echo "✅ Activated virtual environment"

            # 升级 pip（忽略错误）
            python -m pip install --upgrade pip >/dev/null 2>&1 || true

            # 智能安装 requirements.txt
            if [ -f requirements.txt ]; then
              REQ_HASH_FILE=".venv/.reqs.hash"
              NEW_HASH=$(sha256sum requirements.txt | cut -d ' ' -f1)
              OLD_HASH=$(cat "$REQ_HASH_FILE" 2>/dev/null || echo "")
              if [ "$NEW_HASH" != "$OLD_HASH" ]; then
                echo "📦 Installing dependencies from requirements.txt..."
                pip install -r requirements.txt
                echo "$NEW_HASH" > "$REQ_HASH_FILE"
                echo "✅ Dependencies installed and cached."
              else
                echo "✅ requirements.txt unchanged — skipping installation."
              fi
            else
              echo "ℹ️ No requirements.txt found — skipping dependency installation."
            fi

            echo ""
            python --version
            pip --version
            echo "Environment ready ✅"
          '';
        };
      });
    };
}
