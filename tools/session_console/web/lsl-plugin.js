/* Open MCT plugin: LSL streams via the adapter (adapter.py).
 *
 * Object tree:  LSL Streams (root folder) -> one telemetry object per
 * LSL stream, discovered from GET /api/streams.
 * History:      GET /api/history?stream=&start=&end=   (epoch ms)
 * Realtime:     WebSocket on <host>:<http port + 1>
 */
/* global openmct */

function LSLPlugin() {
    const NS = 'lsl';
    const API = '';  // same origin as the page
    const WS_URL = (location.protocol === 'https:' ? 'wss://' : 'ws://')
        + location.hostname + ':' + (parseInt(location.port || '80', 10) + 1);

    let streamCache = null;
    async function getStreams() {
        if (!streamCache) {
            streamCache = fetch(API + '/api/streams').then(r => r.json());
            setTimeout(() => { streamCache = null; }, 10000); // refresh every 10s
        }
        return streamCache;
    }

    function metadataValues(meta) {
        const values = [{
            key: 'utc', source: 't', name: 'Time',
            format: 'utc', hints: { domain: 1 }
        }];
        if (meta.format === 'string') {
            values.push({ key: 'text', name: 'Value', format: 'string',
                          hints: { range: 1 } });
        } else {
            for (let i = 0; i < meta.channels; i++) {
                values.push({ key: 'ch' + i,
                              name: meta.channels > 1 ? 'ch' + i : 'value',
                              hints: { range: i + 1 } });
            }
        }
        return values;
    }

    // ----- realtime: one shared websocket, per-stream callback fanout -----
    const listeners = {};  // stream name -> Set of callbacks
    let ws = null;
    function ensureSocket() {
        if (ws && ws.readyState <= WebSocket.OPEN) return;
        ws = new WebSocket(WS_URL);
        ws.onopen = () => {
            Object.keys(listeners).forEach(name =>
                ws.send(JSON.stringify({ op: 'subscribe', stream: name })));
        };
        ws.onmessage = (ev) => {
            const msg = JSON.parse(ev.data);
            const cbs = listeners[msg.stream];
            if (!cbs) return;
            msg.points.forEach(p => cbs.forEach(cb => cb(p)));
        };
        ws.onclose = () => setTimeout(ensureSocket, 2000);
    }

    return function install(openmct) {
        openmct.types.addType('lsl.telemetry', {
            name: 'LSL Stream',
            description: 'Live Lab Streaming Layer stream via the session console adapter',
            cssClass: 'icon-telemetry',
            creatable: false
        });

        openmct.objects.addRoot({ namespace: NS, key: 'root' });

        openmct.objects.addProvider(NS, {
            get: async (identifier) => {
                if (identifier.key === 'root') {
                    return {
                        identifier, name: 'LSL Streams', type: 'folder',
                        location: 'ROOT'
                    };
                }
                const streams = await getStreams();
                const meta = streams.find(s => s.name === identifier.key);
                if (!meta) {
                    return { identifier, name: identifier.key + ' (offline)',
                             type: 'lsl.telemetry', location: NS + ':root' };
                }
                return {
                    identifier,
                    name: meta.name,
                    type: 'lsl.telemetry',
                    location: NS + ':root',
                    telemetry: { values: metadataValues(meta) }
                };
            }
        });

        openmct.composition.addProvider({
            appliesTo: (domainObject) =>
                domainObject.identifier.namespace === NS &&
                domainObject.identifier.key === 'root',
            load: async () => {
                const streams = await getStreams();
                return streams.map(s => ({ namespace: NS, key: s.name }));
            }
        });

        openmct.telemetry.addProvider({
            supportsRequest: (d) => d.type === 'lsl.telemetry',
            request: async (d, options) => {
                const url = API + '/api/history?stream='
                    + encodeURIComponent(d.identifier.key)
                    + '&start=' + options.start + '&end=' + options.end;
                const resp = await fetch(url).then(r => r.json());
                return resp.data || [];
            },
            supportsSubscribe: (d) => d.type === 'lsl.telemetry',
            subscribe: (d, callback) => {
                const name = d.identifier.key;
                if (!listeners[name]) listeners[name] = new Set();
                listeners[name].add(callback);
                ensureSocket();
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({ op: 'subscribe', stream: name }));
                }
                return () => {
                    listeners[name].delete(callback);
                    if (!listeners[name].size && ws &&
                        ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({ op: 'unsubscribe', stream: name }));
                    }
                };
            }
        });
    };
}
