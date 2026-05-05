<script lang="ts">
  import PixiBoard from '$lib/components/PixiBoard.svelte';
  import {
    addPlayer,
    advanceState,
    buyShopCard,
    createSession,
    listCards,
    removePlayer,
    resolveCombatRound,
    sellFromBoard,
    sellFromHand,
    startShop,
    summonCard,
    transitionPhase
  } from '$lib/api';
  import type { CardDefinition, CardInstance, CombatRoundResponse, PlayerSnapshot, SessionSnapshot } from '$lib/types';

  let seed = 1;
  let playerName = 'Player';
  let session: SessionSnapshot | null = null;
  let catalog: CardDefinition[] = [];
  let lastCombat: CombatRoundResponse | null = null;
  let loading = false;
  let errorMessage = '';

  $: sessionId = session?.metadata.session_id ?? null;
  $: players = session?.players ?? [];
  $: shops = session?.shops ?? [];
  $: events = session?.events.events ?? [];

  async function run<T>(action: () => Promise<T>, apply: (value: T) => void) {
    loading = true;
    errorMessage = '';
    try {
      apply(await action());
    } catch (error) {
      errorMessage = error instanceof Error ? error.message : 'Unexpected error.';
    } finally {
      loading = false;
    }
  }

  async function createNewSession() {
    await run(
      async () => {
        const [created, cards] = await Promise.all([createSession(seed), listCards()]);
        catalog = cards;
        return created;
      },
      (created) => {
        session = created;
        lastCombat = null;
      }
    );
  }

  async function addNamedPlayer() {
    if (!sessionId) return;
    await run(() => addPlayer(sessionId, playerName), (snapshot) => {
      session = snapshot;
      playerName = `Player ${snapshot.players.length + 1}`;
    });
  }

  async function removeExistingPlayer(playerId: string) {
    if (!sessionId) return;
    await run(() => removePlayer(sessionId, playerId), (snapshot) => {
      session = snapshot;
    });
  }

  async function startShopPhase() {
    if (!sessionId) return;
    await run(() => startShop(sessionId), (snapshot) => {
      session = snapshot;
    });
  }

  async function goToPhase(nodeId: string) {
    if (!sessionId) return;
    await run(() => transitionPhase(sessionId, nodeId), (snapshot) => {
      session = snapshot;
    });
  }

  async function advancePhase() {
    if (!sessionId) return;
    await run(() => advanceState(sessionId), (response) => {
      session = response.session;
    });
  }

  async function buy(playerId: string, offerIndex: number) {
    if (!sessionId) return;
    await run(() => buyShopCard(sessionId, playerId, offerIndex), (snapshot) => {
      session = snapshot;
    });
  }

  async function summon(playerId: string, card: CardInstance) {
    if (!sessionId) return;
    await run(() => summonCard(sessionId, playerId, card.instance_id), (snapshot) => {
      session = snapshot;
    });
  }

  async function sellHand(playerId: string, card: CardInstance) {
    if (!sessionId) return;
    await run(() => sellFromHand(sessionId, playerId, card.instance_id), (snapshot) => {
      session = snapshot;
    });
  }

  async function sellBoard(playerId: string, card: CardInstance) {
    if (!sessionId) return;
    await run(() => sellFromBoard(sessionId, playerId, card.instance_id), (snapshot) => {
      session = snapshot;
    });
  }

  async function resolveRound() {
    if (!sessionId) return;
    await run(() => resolveCombatRound(sessionId), (response) => {
      lastCombat = response;
      session = response.session;
    });
  }

  function shopFor(player: PlayerSnapshot) {
    return shops.find((shop) => shop.player_id === player.player_id) ?? null;
  }
</script>

<svelte:head>
  <title>Random Garden</title>
</svelte:head>

<main class="app-shell">
  <section class="topbar">
    <div>
      <p class="eyebrow">Random Garden</p>
      <h1>Engine Control Room</h1>
    </div>
    <div class="session-controls">
      <label>
        Seed
        <input type="number" bind:value={seed} disabled={loading} />
      </label>
      <button on:click={createNewSession} disabled={loading}>New Session</button>
    </div>
  </section>

  {#if errorMessage}
    <p class="error">{errorMessage}</p>
  {/if}

  <section class="workspace">
    <div class="left-column">
      <section class="panel">
        <div class="panel-header">
          <h2>Session</h2>
          {#if session}
            <span>{session.metadata.session_id}</span>
          {/if}
        </div>
        {#if session}
          <div class="metric-grid">
            <span>Phase <strong>{session.metadata.phase ?? 'none'}</strong></span>
            <span>Round <strong>{session.metadata.round_number}</strong></span>
            <span>Turn <strong>{session.metadata.turn_number}</strong></span>
            <span>RNG <strong>{session.metadata.rng_algorithm}</strong></span>
          </div>
          <div class="action-row">
            <button on:click={() => goToPhase('shop')} disabled={loading}>Enter Shop</button>
            <button on:click={() => goToPhase('combat')} disabled={loading}>Enter Combat</button>
            <button on:click={advancePhase} disabled={loading}>Advance</button>
          </div>
        {:else}
          <p class="muted">Create a session to begin.</p>
        {/if}
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Players</h2>
        </div>
        <div class="add-player">
          <input bind:value={playerName} disabled={!session || loading} />
          <button on:click={addNamedPlayer} disabled={!session || loading || !playerName.trim()}>Add</button>
        </div>

        <div class="player-list">
          {#each players as player}
            <article class="player-row">
              <div>
                <strong>{player.name}</strong>
                <span>{player.health}/{player.max_health} HP</span>
              </div>
              <button on:click={() => removeExistingPlayer(player.player_id)} disabled={loading}>Remove</button>
            </article>
          {/each}
        </div>
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Catalog</h2>
          <span>{catalog.length} cards</span>
        </div>
        {#each catalog as card}
          <article class="catalog-card">
            <strong>{card.name}</strong>
            <span>Tier {card.tier ?? '-'} · {card.attack ?? '-'}/{card.health ?? '-'}</span>
            <small>{card.creature_types.join(', ') || card.kind}</small>
          </article>
        {/each}
      </section>
    </div>

    <div class="main-column">
      <section class="panel board-panel">
        <div class="panel-header">
          <h2>Board</h2>
          <button on:click={resolveRound} disabled={!session || loading || players.length < 2}>Resolve Combat</button>
        </div>
        <PixiBoard players={players} />
        {#if lastCombat}
          <p class="combat-summary">
            Last combat: {lastCombat.pair_results.length} pair(s),
            {lastCombat.bye_player_id ? `bye ${lastCombat.bye_player_id}` : 'no bye'}.
          </p>
        {/if}
      </section>

      <section class="panel">
        <div class="panel-header">
          <h2>Shop</h2>
          <button on:click={startShopPhase} disabled={!session || loading}>Start Shop</button>
        </div>
        <div class="shop-grid">
          {#each players as player}
            {@const shop = shopFor(player)}
            <article class="shop-player">
              <header>
                <strong>{player.name}</strong>
                <span>{shop?.economy?.gold ?? 0} gold</span>
              </header>
              <div class="offer-grid">
                {#each shop?.offer?.cards ?? [] as card, index}
                  <button class="mini-card" on:click={() => buy(player.player_id, index)} disabled={loading}>
                    <strong>{card.name}</strong>
                    <span>{card.current_attack ?? '-'}/{card.current_health ?? '-'}</span>
                  </button>
                {/each}
              </div>

              <div class="zone-block">
                <h3>Hand</h3>
                {#each player.hand as card}
                  <div class="zone-card">
                    <span>{card.name} {card.current_attack ?? '-'}/{card.current_health ?? '-'}</span>
                    <div>
                      <button on:click={() => summon(player.player_id, card)} disabled={loading}>Board</button>
                      <button on:click={() => sellHand(player.player_id, card)} disabled={loading}>Sell</button>
                    </div>
                  </div>
                {/each}
              </div>

              <div class="zone-block">
                <h3>Board</h3>
                {#each player.board as card}
                  <div class="zone-card">
                    <span>{card.name} {card.current_attack ?? '-'}/{card.current_health ?? '-'}</span>
                    <button on:click={() => sellBoard(player.player_id, card)} disabled={loading}>Sell</button>
                  </div>
                {/each}
              </div>
            </article>
          {/each}
        </div>
      </section>
    </div>

    <aside class="right-column">
      <section class="panel">
        <div class="panel-header">
          <h2>Events</h2>
          <span>{events.length}</span>
        </div>
        <div class="event-list">
          {#each events.slice(-24).reverse() as event}
            <article>
              <strong>{event.event_type}</strong>
              <code>{event.event_id}</code>
            </article>
          {/each}
        </div>
      </section>
    </aside>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
    background: #0c111b;
    color: #e8eef8;
    font-family:
      Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }

  button,
  input {
    font: inherit;
  }

  button {
    border: 1px solid #3d4d66;
    background: #1d7a6f;
    color: #f8fafc;
    cursor: pointer;
    min-height: 36px;
    padding: 0 12px;
  }

  button:hover:not(:disabled) {
    background: #249181;
  }

  button:disabled {
    cursor: not-allowed;
    opacity: 0.55;
  }

  input {
    min-height: 34px;
    border: 1px solid #334155;
    background: #111827;
    color: #f8fafc;
    padding: 0 10px;
  }

  .app-shell {
    min-height: 100vh;
  }

  .topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
    padding: 22px 28px;
    border-bottom: 1px solid #263244;
    background: #111827;
  }

  .eyebrow {
    color: #5eead4;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 0;
    margin: 0 0 4px;
    text-transform: uppercase;
  }

  h1,
  h2,
  h3,
  p {
    margin: 0;
  }

  h1 {
    font-size: 24px;
  }

  h2 {
    font-size: 16px;
  }

  h3 {
    color: #9fb0c7;
    font-size: 13px;
    margin-bottom: 8px;
  }

  .session-controls,
  .action-row,
  .add-player {
    display: flex;
    align-items: end;
    gap: 10px;
    flex-wrap: wrap;
  }

  label {
    display: grid;
    gap: 4px;
    color: #9fb0c7;
    font-size: 12px;
  }

  .workspace {
    display: grid;
    grid-template-columns: minmax(260px, 320px) minmax(420px, 1fr) minmax(240px, 300px);
    gap: 18px;
    padding: 18px;
  }

  .left-column,
  .main-column,
  .right-column {
    display: grid;
    align-content: start;
    gap: 18px;
  }

  .panel {
    border: 1px solid #263244;
    background: #111827;
    padding: 16px;
  }

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 12px;
    margin-bottom: 14px;
  }

  .panel-header span,
  .muted {
    color: #9fb0c7;
    font-size: 13px;
  }

  .metric-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
    margin-bottom: 14px;
  }

  .metric-grid span {
    background: #0c111b;
    border: 1px solid #263244;
    color: #9fb0c7;
    display: grid;
    gap: 4px;
    padding: 10px;
  }

  .metric-grid strong {
    color: #f8fafc;
  }

  .player-list,
  .event-list {
    display: grid;
    gap: 8px;
  }

  .player-row,
  .zone-card,
  .shop-player header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 10px;
  }

  .player-row {
    border: 1px solid #263244;
    padding: 10px;
  }

  .player-row div {
    display: grid;
    gap: 3px;
  }

  .player-row span,
  .catalog-card span,
  .catalog-card small {
    color: #9fb0c7;
    font-size: 13px;
  }

  .catalog-card {
    border-top: 1px solid #263244;
    display: grid;
    gap: 4px;
    padding: 10px 0;
  }

  .board-panel {
    padding: 0;
  }

  .board-panel .panel-header {
    padding: 16px 16px 0;
  }

  .combat-summary {
    color: #9fb0c7;
    padding: 12px 16px 16px;
  }

  .shop-grid {
    display: grid;
    gap: 14px;
  }

  .shop-player {
    border-top: 1px solid #263244;
    display: grid;
    gap: 12px;
    padding-top: 14px;
  }

  .offer-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  .mini-card {
    align-items: start;
    background: #e8eef8;
    color: #0f172a;
    display: grid;
    gap: 8px;
    min-height: 82px;
    padding: 10px;
    text-align: left;
  }

  .mini-card:hover:not(:disabled) {
    background: #d9f99d;
  }

  .zone-block {
    display: grid;
    gap: 8px;
  }

  .zone-card {
    background: #0c111b;
    border: 1px solid #263244;
    padding: 8px;
  }

  .zone-card div {
    display: flex;
    gap: 6px;
  }

  .event-list {
    max-height: 68vh;
    overflow: auto;
  }

  .event-list article {
    border-bottom: 1px solid #263244;
    display: grid;
    gap: 4px;
    padding: 8px 0;
  }

  code {
    color: #9fb0c7;
    font-size: 12px;
    overflow-wrap: anywhere;
  }

  .error {
    background: #4c1d1d;
    border: 1px solid #ef4444;
    color: #fee2e2;
    margin: 18px 18px 0;
    padding: 12px;
  }

  @media (max-width: 1100px) {
    .workspace {
      grid-template-columns: 1fr;
    }

    .topbar {
      align-items: stretch;
      flex-direction: column;
    }
  }

  @media (max-width: 620px) {
    .workspace,
    .topbar {
      padding: 14px;
    }

    .offer-grid,
    .metric-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
