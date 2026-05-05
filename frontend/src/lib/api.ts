import type {
  CardDefinition,
  CombatRoundResponse,
  SessionSnapshot,
  StateAdvanceResponse
} from '$lib/types';

async function parseJson<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload.detail === 'string'
        ? payload.detail
        : fallbackMessage;
    throw new Error(detail);
  }

  return (await response.json()) as T;
}

export async function getHealth(): Promise<{ status: string }> {
  const response = await fetch('/api/health');
  return parseJson<{ status: string }>(response, 'Backend health check failed.');
}

export async function listCards(): Promise<CardDefinition[]> {
  const response = await fetch('/api/catalog/cards');
  return parseJson<CardDefinition[]>(response, 'Failed to load card catalog.');
}

export async function createSession(seed: number, sessionId?: string): Promise<SessionSnapshot> {
  const response = await fetch('/api/sessions', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      seed,
      session_id: sessionId || null
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to create a session.');
}

export async function getSession(sessionId: string): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
  return parseJson<SessionSnapshot>(response, 'Failed to load the session.');
}

export async function addPlayer(sessionId: string, name: string): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/players`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      name
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to add player.');
}

export async function removePlayer(sessionId: string, playerId: string): Promise<SessionSnapshot> {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/players/${encodeURIComponent(playerId)}`,
    {
      method: 'DELETE'
    }
  );
  return parseJson<SessionSnapshot>(response, 'Failed to remove player.');
}

export async function transitionPhase(sessionId: string, nodeId: string): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/state/transition`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      node_id: nodeId
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to transition phase.');
}

export async function advanceState(sessionId: string): Promise<StateAdvanceResponse> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/state/advance`, {
    method: 'POST'
  });
  return parseJson<StateAdvanceResponse>(response, 'Failed to advance state.');
}

export async function startShop(sessionId: string): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/shop/start`, {
    method: 'POST'
  });
  return parseJson<SessionSnapshot>(response, 'Failed to start shop.');
}

export async function buyShopCard(
  sessionId: string,
  playerId: string,
  offerIndex: number
): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/shop/buy`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      player_id: playerId,
      offer_index: offerIndex
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to buy shop card.');
}

export async function summonCard(
  sessionId: string,
  playerId: string,
  instanceId: string,
  position?: number
): Promise<SessionSnapshot> {
  const response = await fetch(
    `/api/sessions/${encodeURIComponent(sessionId)}/players/${encodeURIComponent(playerId)}/summon`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        instance_id: instanceId,
        position: position ?? null
      })
    }
  );

  return parseJson<SessionSnapshot>(response, 'Failed to summon card.');
}

export async function sellFromHand(
  sessionId: string,
  playerId: string,
  instanceId: string
): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/shop/sell-from-hand`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      player_id: playerId,
      instance_id: instanceId
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to sell card from hand.');
}

export async function sellFromBoard(
  sessionId: string,
  playerId: string,
  instanceId: string
): Promise<SessionSnapshot> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/shop/sell-from-board`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      player_id: playerId,
      instance_id: instanceId
    })
  });

  return parseJson<SessionSnapshot>(response, 'Failed to sell card from board.');
}

export async function resolveCombatRound(sessionId: string): Promise<CombatRoundResponse> {
  const response = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/combat/round`, {
    method: 'POST'
  });
  return parseJson<CombatRoundResponse>(response, 'Failed to resolve combat round.');
}
