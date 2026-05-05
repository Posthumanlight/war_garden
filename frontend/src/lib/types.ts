export type CardKind = 'card' | 'creature' | 'spell';

export interface CardDefinition {
  card_id: string;
  kind: CardKind;
  name: string;
  text: string;
  tags: string[];
  tier: number | null;
  rarity: string | null;
  effect_keys: string[];
  attack: number | null;
  health: number | null;
  creature_types: string[];
  timing: string | null;
  target_rules: string[];
}

export interface CardInstance {
  instance_id: string;
  card_id: string;
  name: string;
  kind: CardKind;
  owner_id: string;
  zone: 'deck' | 'hand' | 'board' | 'graveyard' | 'shop';
  current_attack: number | null;
  current_health: number | null;
  damage: number;
  status_tags: string[];
}

export interface PlayerSnapshot {
  player_id: string;
  name: string;
  health: number;
  max_health: number;
  is_defeated: boolean;
  board: CardInstance[];
  hand: CardInstance[];
  deck: CardInstance[];
  graveyard: CardInstance[];
}

export interface PlayerEconomy {
  gold: number;
  gold_per_round: number;
}

export interface ShopOffer {
  player_id: string;
  cards: CardInstance[];
}

export interface PlayerShop {
  player_id: string;
  economy: PlayerEconomy | null;
  offer: ShopOffer | null;
}

export interface SessionMetadata {
  session_id: string;
  seed: number;
  phase: string | null;
  round_number: number;
  turn_number: number;
  rng_algorithm: string;
  player_count: number;
  active_player_count: number;
  rng_draw_count: number;
}

export interface EngineEvent {
  event_id: string;
  event_type: string;
  payload: Record<string, unknown>;
}

export interface RngDraw {
  draw_index: number;
  purpose: string;
  method: string;
  bounds: Record<string, unknown>;
  result: unknown;
  state_version: number;
}

export interface EventLog {
  events: EngineEvent[];
  rng_draws: RngDraw[];
}

export interface SessionSnapshot {
  metadata: SessionMetadata;
  players: PlayerSnapshot[];
  shops: PlayerShop[];
  events: EventLog;
}

export interface StateAdvanceResponse {
  executed_node_id: string;
  next_node_id: string;
  round_number: number;
  turn_number: number;
  session: SessionSnapshot;
}

export interface CombatResult {
  outcome: string;
  winner_player_id: string | null;
  player_a_id: string;
  player_b_id: string;
  steps: number;
  max_steps_reached: boolean;
  destroyed_instance_ids: string[];
  player_a_living_count: number;
  player_b_living_count: number;
}

export interface PairCombatResult {
  player_a_id: string;
  player_b_id: string;
  combat_result: CombatResult;
}

export interface CombatRoundResponse {
  pair_results: PairCombatResult[];
  bye_player_id: string | null;
  defeated_player_ids: string[];
  session: SessionSnapshot;
}
