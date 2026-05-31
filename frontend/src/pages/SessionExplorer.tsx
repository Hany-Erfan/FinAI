import { useState, useEffect } from 'react';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Endpoints } from '../api/endpoints';
import { useNavigate } from 'react-router-dom';
import { sessionHeaders, csrfHeaders } from '../utils/authUtils';
import './Backoffice.css';
import './SessionExplorer.css';

interface SessionListItem {
    id: string;
    user_id: string | null;
    user_name: string | null;
    status: string;
    created_at: string;
    ended_at: string | null;
    message_count: number;
    has_summary: boolean;
}

interface MessageItem {
    id: string;
    role: string;
    content: string;
    created_at: string;
}

interface SummaryItem {
    summary_text: string;
    key_topics: string[];
    sentiment: string | null;
    resolution_status: string;
    generated_at: string;
    model_used: string | null;
}

interface SessionDetailData {
    id: string;
    user_id: string | null;
    user_name: string | null;
    status: string;
    created_at: string;
    ended_at: string | null;
    messages: MessageItem[];
    summary: SummaryItem | null;
}

interface SessionExplorerProps {
    sessionId: string;
}

const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
};

export default function SessionExplorer({ sessionId }: SessionExplorerProps) {
    const navigate = useNavigate();

    const [sessions, setSessions] = useState<SessionListItem[]>([]);
    const [detail, setDetail] = useState<SessionDetailData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const axiosConfig = {
        headers: {
            ...sessionHeaders(sessionId),
            ...csrfHeaders(sessionId),
        },
        withCredentials: true,
    };

    useEffect(() => {
        fetchSessions();
    }, []);

    const fetchSessions = async () => {
        setLoading(true);
        setError('');
        try {
            const res = await axios.get(Endpoints.ADMIN_SESSIONS, axiosConfig);
            setSessions(res.data);
        } catch (err: any) {
            setError(
                'Failed to load sessions: ' +
                    (err.response?.data?.detail || err.message)
            );
        } finally {
            setLoading(false);
        }
    };

    const fetchDetail = async (id: string) => {
        setLoading(true);
        setError('');
        try {
            const res = await axios.get(
                Endpoints.ADMIN_SESSION_DETAIL(id),
                axiosConfig
            );
            setDetail(res.data);
        } catch (err: any) {
            setError(
                'Failed to load session detail: ' +
                    (err.response?.data?.detail || err.message)
            );
        } finally {
            setLoading(false);
        }
    };

    const handleBack = () => {
        setDetail(null);
        setError('');
    };

    const exportCsv = () => {
        if (!detail) return;

        const escapeCsv = (value: string) => {
            if (value.includes(',') || value.includes('"') || value.includes('\n')) {
                return '"' + value.replace(/"/g, '""') + '"';
            }
            return value;
        };

        const rows: string[][] = [
            ['Session ID', detail.id],
            ['User', detail.user_name || detail.user_id || 'Unknown'],
            ['Status', detail.status],
            ['Created', detail.created_at],
            ['Ended', detail.ended_at || ''],
            [],
            ['Role', 'Content', 'Timestamp'],
            ...detail.messages.map((msg) => [
                msg.role,
                msg.content,
                msg.created_at,
            ]),
        ];

        if (detail.summary) {
            rows.push(
                [],
                ['Summary'],
                ['Text', detail.summary.summary_text],
                ['Key Topics', detail.summary.key_topics.join('; ')],
                ['Sentiment', detail.summary.sentiment || ''],
                ['Resolution', detail.summary.resolution_status],
            );
        }

        const csv = rows.map((r) => r.map(escapeCsv).join(',')).join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `session-${detail.id}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    };

    // ---- Detail View ----
    if (detail) {
        return (
            <div className="backoffice-container">
                <header className="backoffice-header">
                    <h1>Session Detail</h1>
                    <div style={{ display: 'flex', gap: '1rem' }}>
                        <button onClick={() => navigate('/backoffice')} className="btn btn-secondary">
                            Backoffice
                        </button>
                        {/* <button onClick={() => navigate('/guardrails')} className="btn btn-secondary">
                            Guardrails
                        </button> */}
                        <button onClick={handleBack} className="btn btn-secondary">
                            Back to List
                        </button>
                        <button onClick={() => navigate('/chat')} className="btn btn-secondary">
                            Back to Chat
                        </button>
                        <button onClick={exportCsv} className="btn btn-primary">
                            Export CSV
                        </button>
                    </div>
                </header>

                {error && <div className="alert alert-error">{error}</div>}

                <section className="section-card">
                    <div className="session-detail-header">
                        <div>
                            <h2 style={{ margin: 0 }}>
                                {detail.user_name || detail.user_id || 'Unknown User'}
                            </h2>
                            <span className={`status-badge ${detail.status}`}>
                                {detail.status}
                            </span>
                        </div>
                        <dl className="session-meta">
                            <div>
                                <dt>Session ID</dt>
                                <dd style={{ fontSize: '0.8rem', fontFamily: 'monospace' }}>
                                    {detail.id}
                                </dd>
                            </div>
                            <div>
                                <dt>Created</dt>
                                <dd>{formatDate(detail.created_at)}</dd>
                            </div>
                            {detail.ended_at && (
                                <div>
                                    <dt>Ended</dt>
                                    <dd>{formatDate(detail.ended_at)}</dd>
                                </div>
                            )}
                            <div>
                                <dt>Messages</dt>
                                <dd>{detail.messages.length}</dd>
                            </div>
                        </dl>
                    </div>
                </section>

                <section className="section-card">
                    <h3>Conversation</h3>
                    {detail.messages.length === 0 ? (
                        <div className="empty-state">
                            <p>No messages in this session.</p>
                        </div>
                    ) : (
                        <div className="conversation-container">
                            {detail.messages.map((msg) => (
                                <div
                                    key={msg.id}
                                    className={`explorer-message ${msg.role === 'user' ? 'user' : 'agent'}`}
                                >
                                    <span className="explorer-role-label">
                                        {msg.role}
                                    </span>
                                    <div className="explorer-bubble">
                                        {msg.role === 'user' ? (
                                            msg.content
                                        ) : (
                                            <ReactMarkdown remarkPlugins={[remarkGfm]}>
                                                {msg.content}
                                            </ReactMarkdown>
                                        )}
                                        <div className="explorer-timestamp">
                                            {formatDate(msg.created_at)}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </section>

                {detail.summary && (
                    <div className="summary-card">
                        <h3>AI Summary</h3>
                        <div className="summary-text">{detail.summary.summary_text}</div>

                        {detail.summary.key_topics.length > 0 && (
                            <div className="summary-topics">
                                {detail.summary.key_topics.map((topic) => (
                                    <span key={topic} className="topic-chip">
                                        {topic}
                                    </span>
                                ))}
                            </div>
                        )}

                        <div className="summary-meta">
                            {detail.summary.sentiment && (
                                <span>Sentiment: <strong>{detail.summary.sentiment}</strong></span>
                            )}
                            <span>
                                Resolution: <strong>{detail.summary.resolution_status}</strong>
                            </span>
                            <span>Generated: {formatDate(detail.summary.generated_at)}</span>
                        </div>
                    </div>
                )}
            </div>
        );
    }

    // ---- List View ----
    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Session Explorer</h1>
                <div style={{ display: 'flex', gap: '1rem' }}>
                    <button onClick={() => navigate('/backoffice')} className="btn btn-secondary">
                        Document Backoffice
                    </button>
                    {/* <button onClick={() => navigate('/guardrails')} className="btn btn-secondary">
                        Guardrails Management
                    </button> */}
                    <button onClick={() => navigate('/chat')} className="btn btn-secondary">
                        Back to Chat
                    </button>
                </div>
            </header>

            {error && <div className="alert alert-error">{error}</div>}

            <section className="section-card">
                <h2 style={{ margin: '0 0 1rem 0' }}>
                    All Sessions ({sessions.length})
                </h2>

                {loading && sessions.length === 0 ? (
                    <div className="empty-state">
                        <p>Loading sessions...</p>
                    </div>
                ) : sessions.length === 0 ? (
                    <div className="empty-state">
                        <p>No sessions found.</p>
                    </div>
                ) : (
                    <div className="table-container">
                        <table className="product-table session-table">
                            <thead>
                                <tr>
                                    <th>User</th>
                                    <th>Status</th>
                                    <th>Created</th>
                                    <th>Ended</th>
                                    <th>Messages</th>
                                    <th>Summary</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sessions.map((s) => (
                                    <tr
                                        key={s.id}
                                        className="clickable-row"
                                        onClick={() => fetchDetail(s.id)}
                                    >
                                        <td data-label="User">{s.user_name || s.user_id || '-'}</td>
                                        <td data-label="Status">
                                            <span className={`status-badge ${s.status}`}>
                                                {s.status}
                                            </span>
                                        </td>
                                        <td data-label="Created">{formatDate(s.created_at)}</td>
                                        <td data-label="Ended">{s.ended_at ? formatDate(s.ended_at) : '-'}</td>
                                        <td data-label="Messages">{s.message_count}</td>
                                        <td data-label="Summary">
                                            <span
                                                className={`summary-indicator ${s.has_summary ? 'has-summary' : 'no-summary'}`}
                                                title={s.has_summary ? 'Summary available' : 'No summary'}
                                            />
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </section>
        </div>
    );
}
