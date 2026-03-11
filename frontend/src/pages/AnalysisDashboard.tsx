import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import { Endpoints } from '../api/endpoints';
import { useNavigate } from 'react-router-dom';
import { sessionHeaders, csrfHeaders } from '../utils/authUtils';
import './Backoffice.css';
import './AnalysisDashboard.css';

interface TimeSeriesPoint {
    timestamp: string;
    value: number;
}

interface LanguageCount {
    language: string;
    count: number;
}

interface AnalyticsData {
    total_sessions: number;
    total_sessions_series: TimeSeriesPoint[];
    containment_rate: number;
    escalated_count: number;
    avg_response_time: number | null;
    response_time_series: TimeSeriesPoint[];
    language_distribution: LanguageCount[];
}

interface AnalysisDashboardProps {
    sessionId: string;
}

const TIME_RANGES = [
    { label: '1h', hours: 1 },
    { label: '6h', hours: 6 },
    { label: '24h', hours: 24 },
    { label: '7d', hours: 168 },
    { label: '30d', hours: 720 },
];

const DONUT_COLORS = ['#007bff', '#28a745', '#ffc107', '#dc3545', '#6f42c1', '#17a2b8'];

// ---------------------------------------------------------------------------
// SVG Visualisation Helpers
// ---------------------------------------------------------------------------

function Sparkline({ data }: { data: TimeSeriesPoint[] }) {
    if (data.length === 0) return null;
    const values = data.map(d => d.value);
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const w = 300;
    const h = 60;
    const points = values.map((v, i) => {
        const x = (i / Math.max(values.length - 1, 1)) * w;
        const y = h - ((v - min) / (max - min || 1)) * h;
        return `${x},${y}`;
    }).join(' ');
    const areaPoints = `0,${h} ${points} ${w},${h}`;
    return (
        <div className="sparkline-container">
            <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
                <polyline fill="none" stroke="#007bff" strokeWidth="2" points={points} />
                <polygon fill="rgba(0,123,255,0.1)" points={areaPoints} />
            </svg>
        </div>
    );
}

function GaugeChart({ value }: { value: number }) {
    const r = 60;
    const cx = 70;
    const cy = 70;
    const circumference = Math.PI * r; // semi-circle
    const pct = Math.min(Math.max(value, 0), 100);
    const filled = (pct / 100) * circumference;
    let color = '#dc3545'; // red
    if (pct >= 80) color = '#28a745'; // green
    else if (pct >= 50) color = '#ffc107'; // yellow

    return (
        <div className="gauge-container">
            <svg width="140" height="80" viewBox="0 0 140 80">
                <path
                    d={`M 10 70 A ${r} ${r} 0 0 1 130 70`}
                    fill="none"
                    stroke="#e9ecef"
                    strokeWidth="12"
                    strokeLinecap="round"
                />
                <path
                    d={`M 10 70 A ${r} ${r} 0 0 1 130 70`}
                    fill="none"
                    stroke={color}
                    strokeWidth="12"
                    strokeLinecap="round"
                    strokeDasharray={`${filled} ${circumference}`}
                />
            </svg>
            <span className="gauge-value" style={{ color }}>{value.toFixed(1)}%</span>
            <span className="gauge-subtitle">Containment Rate</span>
        </div>
    );
}

function LineChart({ data }: { data: TimeSeriesPoint[] }) {
    if (data.length === 0) return <div className="dashboard-loading">No data</div>;
    const values = data.map(d => d.value);
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const padding = { top: 10, right: 10, bottom: 25, left: 40 };
    const w = 400;
    const h = 180;
    const plotW = w - padding.left - padding.right;
    const plotH = h - padding.top - padding.bottom;

    const points = values.map((v, i) => {
        const x = padding.left + (i / Math.max(values.length - 1, 1)) * plotW;
        const y = padding.top + plotH - ((v - min) / (max - min || 1)) * plotH;
        return `${x},${y}`;
    }).join(' ');

    const yTicks = 4;
    const yLabels: { y: number; label: string }[] = [];
    for (let i = 0; i <= yTicks; i++) {
        const val = min + (max - min) * (i / yTicks);
        const y = padding.top + plotH - (i / yTicks) * plotH;
        yLabels.push({ y, label: val.toFixed(1) });
    }

    return (
        <div className="line-chart-container">
            <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none">
                {/* grid lines */}
                {yLabels.map((t, i) => (
                    <g key={i}>
                        <line x1={padding.left} y1={t.y} x2={w - padding.right} y2={t.y}
                              stroke="#e9ecef" strokeWidth="1" />
                        <text x={padding.left - 5} y={t.y + 3} textAnchor="end"
                              fontSize="9" fill="#888">{t.label}s</text>
                    </g>
                ))}
                <polyline fill="none" stroke="#007bff" strokeWidth="2" points={points} />
            </svg>
        </div>
    );
}

function DonutChart({ data }: { data: LanguageCount[] }) {
    const total = data.reduce((s, d) => s + d.count, 0);
    if (total === 0) return <div className="dashboard-loading">No data</div>;

    const segments: string[] = [];
    let cumPct = 0;
    data.forEach((d, i) => {
        const pct = (d.count / total) * 100;
        segments.push(`${DONUT_COLORS[i % DONUT_COLORS.length]} ${cumPct}% ${cumPct + pct}%`);
        cumPct += pct;
    });

    const gradient = `conic-gradient(${segments.join(', ')})`;

    return (
        <div className="donut-container">
            <div className="donut-chart" style={{ background: gradient }}>
                <div className="donut-hole" />
            </div>
            <div className="donut-legend">
                {data.map((d, i) => (
                    <div key={d.language} className="donut-legend-item">
                        <span className="donut-legend-swatch"
                              style={{ background: DONUT_COLORS[i % DONUT_COLORS.length] }} />
                        <span>{d.language}: {d.count} ({((d.count / total) * 100).toFixed(1)}%)</span>
                    </div>
                ))}
            </div>
        </div>
    );
}

// ---------------------------------------------------------------------------
// Main Component
// ---------------------------------------------------------------------------

export default function AnalysisDashboard({ sessionId }: AnalysisDashboardProps) {
    const navigate = useNavigate();
    const [data, setData] = useState<AnalyticsData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [rangeIdx, setRangeIdx] = useState(1); // default 6h

    const axiosConfig = {
        headers: {
            ...sessionHeaders(sessionId),
            ...csrfHeaders(sessionId),
        },
        withCredentials: true,
    };

    const fetchData = useCallback(async (hours: number) => {
        setLoading(true);
        setError('');
        const end = new Date().toISOString();
        const start = new Date(Date.now() - hours * 3600_000).toISOString();
        try {
            const res = await axios.get(
                Endpoints.ADMIN_ANALYTICS(start, end),
                axiosConfig,
            );
            setData(res.data);
        } catch (err: any) {
            setError(
                'Failed to load analytics: ' +
                (err.response?.data?.detail || err.message),
            );
        } finally {
            setLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        fetchData(TIME_RANGES[rangeIdx].hours);
    }, [rangeIdx]);

    const handleRange = (idx: number) => {
        setRangeIdx(idx);
    };

    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Analysis Dashboard</h1>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <button onClick={() => navigate('/chat')} className="btn btn-secondary">Back to Chat</button>
                    <button onClick={() => navigate('/backoffice')} className="btn btn-secondary">Document Backoffice</button>
                    <button onClick={() => navigate('/session-explorer')} className="btn btn-primary">Session Explorer</button>
                </div>
            </header>

            {error && <div className="alert alert-error">{error}</div>}

            <div style={{ marginBottom: '1.5rem' }}>
                <div className="dashboard-time-range">
                    {TIME_RANGES.map((r, i) => (
                        <button
                            key={r.label}
                            className={i === rangeIdx ? 'active' : ''}
                            onClick={() => handleRange(i)}
                        >
                            {r.label}
                        </button>
                    ))}
                </div>
            </div>

            {loading && !data ? (
                <div className="dashboard-loading">Loading analytics...</div>
            ) : data ? (
                <div className="dashboard-grid">
                    {/* Total Sessions */}
                    <div className="dashboard-panel">
                        <h3>Total Sessions</h3>
                        <span className="stat-big-number">{data.total_sessions}</span>
                        <Sparkline data={data.total_sessions_series} />
                    </div>

                    {/* Containment Rate */}
                    <div className="dashboard-panel">
                        <h3>Containment Rate</h3>
                        <GaugeChart value={data.containment_rate} />
                        <div style={{ textAlign: 'center', fontSize: '0.85rem', color: '#888' }}>
                            {data.escalated_count} escalated of {data.total_sessions} sessions
                        </div>
                    </div>

                    {/* Avg Response Time */}
                    <div className="dashboard-panel">
                        <h3>Avg Response Time</h3>
                        <span className="rt-big-number">
                            {data.avg_response_time != null ? `${data.avg_response_time}s` : 'N/A'}
                        </span>
                        <LineChart data={data.response_time_series} />
                    </div>

                    {/* Language Distribution */}
                    <div className="dashboard-panel">
                        <h3>Language Distribution</h3>
                        <DonutChart data={data.language_distribution} />
                    </div>
                </div>
            ) : null}
        </div>
    );
}
