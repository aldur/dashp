{
  inputs = { nixpkgs.url = "nixpkgs/nixos-unstable"; };
  outputs = { nixpkgs, ... }:
    let
      forAllSystems = function:
        nixpkgs.lib.genAttrs [
          "x86_64-linux"
          "aarch64-linux"
          "x86_64-darwin"
          "aarch64-darwin"
        ] (system: function nixpkgs.legacyPackages.${system});
    in {

      packages =
        forAllSystems (pkgs: { default = pkgs.callPackage ./dashp.nix { }; });

    };
}
