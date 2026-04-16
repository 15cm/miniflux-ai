{
  description = "miniflux-ai development environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python312;
        pythonEnv = python.withPackages (ps: with ps; [
          # Production deps
          flask
          jinja2
          pyyaml
          markdown
          markdownify
          schedule
          feedgen
          requests
          # Dev deps
          pytest
          pytest-cov
          black
          flake8
          mypy
        ]);
      in
      {
        devShells.default = pkgs.mkShell {
          packages = [ pythonEnv ];

          shellHook = ''
            echo "miniflux-ai env ready ($(python --version))"
          '';
        };
      }
    );
}
