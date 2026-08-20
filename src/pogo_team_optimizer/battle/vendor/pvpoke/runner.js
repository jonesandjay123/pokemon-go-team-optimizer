#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function fail(message) {
  process.stderr.write(`${message}\n`);
  process.exit(1);
}

function readRequest() {
  const raw = fs.readFileSync(0, "utf8");
  if (!raw.trim()) fail("empty PvPoke bridge request");
  return JSON.parse(raw);
}

function installBrowserStubs(gameMasterData) {
  global.host = "localhost";
  global.webRoot = "";
  global.siteVersion = "v3-bridge";
  global.settings = { gamemaster: "gamemaster" };
  global.window = { localStorage: { getItem: () => null, setItem: () => {} } };
  const dollar = () => ({
    insertAfter: () => {},
    eq: () => ({}),
  });
  const pendingAjax = [];
  dollar.ajax = (options) => pendingAjax.push(options);
  dollar.each = (collection, callback) => {
      if (Array.isArray(collection)) {
        collection.forEach((value, index) => callback(index, value));
      } else {
        Object.entries(collection).forEach(([key, value]) => callback(key, value));
      }
    };
  global.$ = dollar;
  global.__flushPvPokeAjax = () => {
    while (pendingAjax.length) pendingAjax.shift().success(gameMasterData);
  };
}

function loadPvPoke() {
  const files = [
    "DamageCalculator.js",
    "actions/ActionLogic.js",
    "timeline/TimelineEvent.js",
    "timeline/TimelineAction.js",
    "training/DecisionOption.js",
    "GameMaster.js",
    "Pokemon.js",
    "Battle.js",
  ];
  const source = files
    .map((file) => fs.readFileSync(path.join(__dirname, file), "utf8"))
    .join("\n\n");
  vm.runInThisContext(
    `${source}\n;globalThis.__pvpokeBridge = { GameMaster, Pokemon, Battle };`,
    { filename: "pvpoke-vendored.js" },
  );
  return global.__pvpokeBridge;
}

function chooseMoves(pokemon, moveset) {
  const legalFast = new Set(pokemon.fastMovePool.map((move) => move.moveId));
  const legalCharged = new Set(pokemon.chargedMovePool.map((move) => move.moveId));
  if (!legalFast.has(moveset.fast_move)) {
    throw new Error(`${moveset.fast_move} is not legal for ${moveset.species_id}`);
  }
  for (const move of moveset.charged_moves) {
    if (!legalCharged.has(move)) {
      throw new Error(`${move} is not legal for ${moveset.species_id}`);
    }
  }
  pokemon.selectMove("fast", moveset.fast_move, 0, true);
  moveset.charged_moves.forEach((move, index) => {
    pokemon.selectMove("charged", move, index, true);
  });
  if (moveset.charged_moves.length < 2) {
    pokemon.selectMove("charged", "none", 1, true);
  }
  const selected = [
    pokemon.fastMove && pokemon.fastMove.moveId,
    ...pokemon.chargedMoves.map((move) => move && move.moveId),
  ];
  const expected = [moveset.fast_move, ...moveset.charged_moves];
  if (selected.length !== expected.length || selected.some((move, i) => move !== expected[i])) {
    throw new Error(
      `illegal or unresolved moveset for ${moveset.species_id}: expected ${expected.join("/")}, selected ${selected.join("/")}`,
    );
  }
}

function buildSummary(pokemon) {
  return {
    species_id: pokemon.speciesId,
    cp: pokemon.cp,
    level: pokemon.level,
    ivs: { ...pokemon.ivs },
    max_hp: pokemon.stats.hp,
    attack: pokemon.stats.atk,
    defense: pokemon.stats.def,
  };
}

function simulateOne(Pokemon, Battle, request, matchup) {
  const battle = new Battle();
  battle.setCP(request.cp_cap || 1500);
  battle.setLevelCap(request.level_cap || 50);
  battle.setBuffChanceModifier(-1);

  const candidate = new Pokemon(matchup.candidate.species_id, 0, battle);
  const opponent = new Pokemon(matchup.opponent.species_id, 1, battle);
  if (!candidate.data) throw new Error(`unknown candidate: ${matchup.candidate.species_id}`);
  if (!opponent.data) throw new Error(`unknown opponent: ${matchup.opponent.species_id}`);

  battle.setNewPokemon(candidate, 0, true);
  battle.setNewPokemon(opponent, 1, true);
  chooseMoves(candidate, matchup.candidate);
  chooseMoves(opponent, matchup.opponent);

  candidate.setShields(matchup.shields);
  opponent.setShields(matchup.shields);
  candidate.setStartEnergy(0);
  opponent.setStartEnergy(0);
  candidate.setStartHp(0);
  opponent.setStartHp(0);

  const candidateBuild = buildSummary(candidate);
  const opponentBuild = buildSummary(opponent);
  battle.simulate();
  const ratings = battle.getBattleRatings();

  return {
    request_id: matchup.request_id,
    shields: matchup.shields,
    candidate_rating: ratings[0],
    opponent_rating: ratings[1],
    outcome: ratings[0] > 500 ? "win" : ratings[0] < 500 ? "loss" : "tie",
    candidate_remaining_hp: candidate.hp,
    opponent_remaining_hp: opponent.hp,
    candidate_build: candidateBuild,
    opponent_build: opponentBuild,
  };
}

try {
  const request = readRequest();
  const gameMasterData = JSON.parse(fs.readFileSync(request.gamemaster_path, "utf8"));
  installBrowserStubs(gameMasterData);

  // Upstream logs GameMaster loading progress; JSON is the only stdout protocol.
  const originalLog = console.log;
  console.log = () => {};
  const { GameMaster, Pokemon, Battle } = loadPvPoke();
  const gm = GameMaster.getInstance();
  global.__flushPvPokeAjax();
  console.log = originalLog;
  if (!gm || !gm.data || !gm.data.pokemon) fail("PvPoke GameMaster failed to initialize");

  const results = request.matchups.map((matchup) =>
    simulateOne(Pokemon, Battle, request, matchup),
  );
  process.stdout.write(JSON.stringify({ results }));
} catch (error) {
  fail(error && error.stack ? error.stack : String(error));
}
