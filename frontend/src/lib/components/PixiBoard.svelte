<script lang="ts">
  import { onMount } from 'svelte';
  import type { PlayerSnapshot } from '$lib/types';

  export let players: PlayerSnapshot[] = [];

  let host: HTMLDivElement;
  let app: import('pixi.js').Application | null = null;
  let pixi: typeof import('pixi.js') | null = null;

  onMount(() => {
    let disposed = false;
    void initializePixi(() => disposed);

    return () => {
      disposed = true;
      app?.destroy(true, { children: true });
      app = null;
    };
  });

  $: if (app && pixi) {
    draw();
  }

  async function initializePixi(isDisposed: () => boolean) {
    const runtime = await import('pixi.js');
    if (isDisposed()) {
      return;
    }
    pixi = runtime;
    app = new runtime.Application();
    await app.init({
      background: '#10151f',
      antialias: true,
      resizeTo: host
    });
    if (isDisposed()) {
      app.destroy(true, { children: true });
      app = null;
      return;
    }
    host.appendChild(app.canvas);
    draw();
  }

  function draw() {
    const runtime = pixi;
    if (!app || !runtime) {
      return;
    }

    const width = Math.max(host?.clientWidth ?? 900, 320);
    const height = Math.max(host?.clientHeight ?? 360, 320);
    app.renderer.resize(width, height);
    app.stage.removeChildren();

    const background = new runtime.Graphics();
    background.rect(0, 0, width, height).fill(0x10151f);
    app.stage.addChild(background);

    if (players.length === 0) {
      addText('Create a session to render boards.', width / 2 - 130, height / 2 - 12, 16, 0xb8c4d8);
      return;
    }

    const visiblePlayers = players.slice(0, 2);
    const laneHeight = height / 2;
    visiblePlayers.forEach((player, laneIndex) => {
      const laneY = laneIndex * laneHeight;
      const lane = new runtime.Graphics();
      lane.rect(0, laneY, width, laneHeight - 1).fill(laneIndex === 0 ? 0x151c29 : 0x111827);
      lane.rect(0, laneY + laneHeight - 1, width, 1).fill(0x263244);
      app?.stage.addChild(lane);

      addText(`${player.name}  ${player.health}/${player.max_health}`, 18, laneY + 14, 16, 0xf8fafc);

      const cardWidth = Math.min(104, Math.max(72, (width - 48) / 7 - 8));
      const cardHeight = Math.min(132, laneHeight - 70);
      const startX = 18;
      const cardY = laneY + 54;

      player.board.forEach((card, index) => {
        const x = startX + index * (cardWidth + 8);
        const cardShape = new runtime.Graphics();
        const fill = card.current_health && card.current_health > 0 ? 0xe8eef8 : 0x5f6877;
        cardShape.roundRect(x, cardY, cardWidth, cardHeight, 8).fill(fill);
        cardShape.roundRect(x, cardY, cardWidth, cardHeight, 8).stroke({ width: 2, color: 0x4f8cff });
        app?.stage.addChild(cardShape);

        addText(card.name, x + 8, cardY + 10, 13, 0x101827, cardWidth - 16);
        addText(`${card.current_attack ?? '-'} / ${card.current_health ?? '-'}`, x + 10, cardY + cardHeight - 30, 18, 0x0f172a);
      });

      if (player.board.length === 0) {
        addText('Empty board', 18, cardY + 38, 14, 0x8ea0ba);
      }
    });
  }

  function addText(text: string, x: number, y: number, size: number, color: number, wordWrapWidth = 260) {
    const runtime = pixi;
    if (!app || !runtime) {
      return;
    }
    const label = new runtime.Text({
      text,
      style: {
        fontFamily: 'Arial, sans-serif',
        fontSize: size,
        fill: color,
        wordWrap: true,
        wordWrapWidth
      }
    });
    label.x = x;
    label.y = y;
    app.stage.addChild(label);
  }
</script>

<div class="pixi-host" bind:this={host}></div>

<style>
  .pixi-host {
    min-height: 360px;
    height: 44vh;
    width: 100%;
    overflow: hidden;
    border: 1px solid #263244;
    background: #10151f;
  }

  :global(canvas) {
    display: block;
  }
</style>
