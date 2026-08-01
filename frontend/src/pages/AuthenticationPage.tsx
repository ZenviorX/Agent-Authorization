import type {
  LiveConnectionState,
  LiveRuntimeSnapshot,
  ServiceHealthState
} from '../types/domain';

function serviceLabel(status?: ServiceHealthState) {
  if (status === 'online') return '在线';
  if (status === 'offline') return '离线';
  return '等待状态';
}

function serviceTone(status?: ServiceHealthState) {
  if (status === 'online') return 'online';
  if (status === 'offline') return 'offline';
  return 'unknown';
}

function connectionLabel(state: LiveConnectionState) {
  if (state === 'live') return '实时状态已连接';
  if (state === 'degraded') return '部分状态不可用';
  if (state === 'offline') return '后端连接中断';
  return '正在连接后端';
}

export function AuthenticationPage({
  snapshot,
  connectionState
}: {
  snapshot: LiveRuntimeSnapshot | null;
  connectionState: LiveConnectionState;
}) {
  const oauth = snapshot?.services.oauth;
  const mcp = snapshot?.services.mcp;
  const backend = snapshot?.services.backend;

  const mcpEndpoint =
    snapshot?.systemStatus.mcp?.endpoint
    || snapshot?.mcpStatus?.endpoint
    || 'http://127.0.0.1:8000/mcp';

  const metadataEndpoint =
    snapshot?.systemStatus.mcp?.protected_resource_metadata
    || snapshot?.mcpStatus?.protected_resource_metadata
    || 'http://127.0.0.1:8000/.well-known/oauth-protected-resource';

  const oauthIssuer =
    snapshot?.mcpStatus?.oauth_issuer
    || snapshot?.systemStatus.mcp?.demo_authorization_server
    || 'http://127.0.0.1:9000';

  const protocol =
    snapshot?.systemStatus.mcp?.protocol_target
    || snapshot?.mcpStatus?.protocol_target
    || '等待协议状态';

  const infrastructureReady =
    oauth?.status === 'online'
    && mcp?.status === 'online'
    && backend?.status === 'online';

  return (
    <div className="authentication-page">
      <section className="authentication-hero">
        <div>
          <span className="eyebrow">MCP + OAuth</span>
          <h2>认证基础设施与协议状态</h2>
          <p>
            展示 OAuth Authorization Server、MCP Protected Resource 和 FastAPI 后端的实时状态，
            并说明标准认证流程如何进入 AgentGuard 安全链路。
          </p>
        </div>
        <div className={`authentication-summary auth-summary-${infrastructureReady ? 'ready' : 'waiting'}`}>
          <span>{connectionLabel(connectionState)}</span>
          <strong>{infrastructureReady ? '认证基础设施在线' : '等待服务就绪'}</strong>
          <small>
            此状态表示认证相关服务是否可用，不代表某个 MCP Client 已经取得 Access Token。
          </small>
        </div>
      </section>

      <section className="authentication-service-grid">
        <article className="authentication-service-card">
          <div className="authentication-card-head">
            <span className={`authentication-status-dot status-${serviceTone(oauth?.status)}`} />
            <span>OAuth Authorization Server</span>
            <strong>{serviceLabel(oauth?.status)}</strong>
          </div>
          <h3>身份授权与 Access Token 签发</h3>
          <code>{oauthIssuer}</code>
          <p>{oauth?.detail || '等待 OAuth Demo Server 状态同步。'}</p>
        </article>

        <article className="authentication-service-card">
          <div className="authentication-card-head">
            <span className={`authentication-status-dot status-${serviceTone(mcp?.status)}`} />
            <span>MCP Protected Resource</span>
            <strong>{serviceLabel(mcp?.status)}</strong>
          </div>
          <h3>Bearer Token 保护的 JSON-RPC 入口</h3>
          <code>{mcpEndpoint}</code>
          <p>{mcp?.detail || '等待 MCP Gateway 状态同步。'}</p>
        </article>

        <article className="authentication-service-card">
          <div className="authentication-card-head">
            <span className={`authentication-status-dot status-${serviceTone(backend?.status)}`} />
            <span>AgentGuard Backend</span>
            <strong>{serviceLabel(backend?.status)}</strong>
          </div>
          <h3>任务边界、令牌、沙箱与审计</h3>
          <code>{snapshot?.systemStatus.execution_entrypoint || '等待执行入口状态'}</code>
          <p>{backend?.detail || '等待 FastAPI 后端状态同步。'}</p>
        </article>
      </section>

      <section className="authentication-details">
        <div className="authentication-detail-card">
          <span>OAuth Protected Resource Metadata</span>
          <code>{metadataEndpoint}</code>
        </div>
        <div className="authentication-detail-card">
          <span>MCP Protocol Target</span>
          <code>{protocol}</code>
        </div>
        <div className="authentication-detail-card">
          <span>Transport</span>
          <code>JSON-RPC 2.0 · POST /mcp · Bearer Access Token</code>
        </div>
      </section>

      <section className="authentication-flow-section">
        <div className="authentication-section-heading">
          <span className="eyebrow">Authentication Flow</span>
          <h2>从认证到工具调用</h2>
          <p>OAuth 负责身份和粗粒度 Scope，AgentGuard 继续检查当前任务、参数和运行时数据流。</p>
        </div>

        <div className="authentication-flow">
          <div><strong>MCP Client 请求资源</strong><span>首次请求没有有效凭证</span></div>
          <b>→</b>
          <div><strong>401 + Resource Metadata</strong><span>发现 OAuth Server 和支持的 Scope</span></div>
          <b>→</b>
          <div><strong>Authorization Code + PKCE</strong><span>用户授权后交换 Access Token</span></div>
          <b>→</b>
          <div><strong>Bearer Token 请求 MCP</strong><span>校验签名、Issuer、Audience、Expiry 与 Scope</span></div>
          <b>→</b>
          <div><strong>AgentGuard 安全链</strong><span>Task Boundary → Token → Sandbox → Evidence</span></div>
        </div>
      </section>
    </div>
  );
}
