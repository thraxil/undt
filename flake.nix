{
  description = "Python development environment with uv";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = import nixpkgs { inherit system; };
        python = pkgs.python313;
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [
            python
            pkgs.uv
          ];

          env = {
            # Use the nixpkgs interpreter instead of letting uv download its own.
            UV_PYTHON_DOWNLOADS = "never";
            UV_PYTHON = python.interpreter;
          };

          shellHook = ''
            unset PYTHONPATH
            export UV_PROJECT_ENVIRONMENT="$PWD/.venv"
          '';
        };
      });
}
