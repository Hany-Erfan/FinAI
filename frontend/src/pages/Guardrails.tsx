import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Endpoints } from '../api/endpoints';
import { useNavigate } from 'react-router-dom';
import { sessionHeaders, csrfHeaders } from '../utils/authUtils';
import './Backoffice.css';
import './Guardrails.css';

interface GuardrailsConfig {
    is_safe_input: boolean;
    enforce_anonymous_mode: boolean;
    block_financial_advisory: boolean;
    escalation_trigger: boolean;
    restrict_to_topic: boolean;
    detect_pii_input: boolean;
    secrets_present_input: boolean;
    toxic_language: boolean;
    detect_pii_output: boolean;
    secrets_present_output: boolean;
    is_safe_output: boolean;
    valid_topics: string[];
    invalid_topics: string[];
}

interface GuardrailsProps {
    sessionId: string;
}

const validatorDescriptions: Record<string, string> = {
    is_safe_input: "Analyzes user input for common LLM injection patterns, prompt leakage attempts, and dangerous command keywords like 'DROP TABLE' or 'BYPASS'.",
    enforce_anonymous_mode: "Ensures privacy by blocking requests that contain phrases related to personal bank accounts, balances, or specific transactions, keeping the session anonymous.",
    block_financial_advisory: "Prevents the model from giving specific investment advice or recommending financial products beyond general information, mitigating legal risks.",
    escalation_trigger: "Monitors for high-sensitivity keywords like 'fraud', 'stolen', or 'lawsuit', and automatically flags the conversation for immediate human intervention.",
    restrict_to_topic: "Uses semantic analysis to ensure the user's query is relevant to the allowed banking topics. Messages outside these topics will be blocked.",
    detect_pii_input: "Scans for and blocks sensitive Personal Identifiable Information (PII) like emails, phone numbers, and SSNs from being processed by the LLM.",
    secrets_present_input: "Detects the presence of sensitive credentials, API keys, or passwords in the user's message to prevent accidental exposure.",
    toxic_language: "Uses an advanced multilingual LLM to filter out offensive, hateful, or inappropriate language to maintain a professional environment.",
    detect_pii_output: "Ensures the AI agent does not inadvertently leak sensitive data in its response, providing a final layer of protection for customer privacy.",
    secrets_present_output: "Verifies that the AI's generated response doesn't contain any internal system keys, tokens, or back-end secrets.",
    is_safe_output: "A final catch-all safety check to ensure the response is helpful, professional, and doesn't contain any restricted content."
};

export default function Guardrails({ sessionId }: GuardrailsProps) {
    const [config, setConfig] = useState<GuardrailsConfig | null>(null);
    const [savingConfig, setSavingConfig] = useState(false);
    const [message, setMessage] = useState('');
    const [newTopic, setNewTopic] = useState('');
    const [newInvalidTopic, setNewInvalidTopic] = useState('');
    const [activeTooltip, setActiveTooltip] = useState<string | null>(null);

    const navigate = useNavigate();

    const axiosConfig = {
        headers: {
            ...sessionHeaders(sessionId),
            ...csrfHeaders(sessionId)
        },
        withCredentials: true
    };

    useEffect(() => {
        fetchConfig();
    }, []);

    const fetchConfig = async () => {
        try {
            const res = await axios.get(Endpoints.GUARDRAILS_CONFIG, axiosConfig);
            if (res.data) {
                setConfig(res.data);
            }
        } catch (err) {
            console.error("Failed to fetch configuration", err);
        }
    };

    const handleConfigToggle = (key: keyof GuardrailsConfig) => {
        if (!config) return;
        setConfig({ ...config, [key]: !config[key as keyof GuardrailsConfig] });
    };

    const handleAddTopic = () => {
        if (!config || !newTopic.trim()) return;
        if (config.valid_topics.includes(newTopic.trim())) {
            setNewTopic('');
            return;
        }
        setConfig({
            ...config,
            valid_topics: [...config.valid_topics, newTopic.trim()]
        });
        setNewTopic('');
    };

    const handleRemoveTopic = (topic: string) => {
        if (!config) return;
        setConfig({
            ...config,
            valid_topics: config.valid_topics.filter(t => t !== topic)
        });
    };

    const handleAddInvalidTopic = () => {
        if (!config || !newInvalidTopic.trim()) return;
        if (config.invalid_topics.includes(newInvalidTopic.trim())) {
            setNewInvalidTopic('');
            return;
        }
        setConfig({
            ...config,
            invalid_topics: [...config.invalid_topics, newInvalidTopic.trim()]
        });
        setNewInvalidTopic('');
    };

    const handleRemoveInvalidTopic = (topic: string) => {
        if (!config) return;
        setConfig({
            ...config,
            invalid_topics: config.invalid_topics.filter(t => t !== topic)
        });
    };

    const handleSelectAllValidators = () => {
        if (!config) return;
        const newConfig = { ...config };
        Object.keys(validatorDescriptions).forEach(key => {
            (newConfig as any)[key] = true;
        });
        setConfig(newConfig);
    };

    const handleDeselectAllValidators = () => {
        if (!config) return;
        const newConfig = { ...config };
        Object.keys(validatorDescriptions).forEach(key => {
            (newConfig as any)[key] = false;
        });
        setConfig(newConfig);
    };

    const handleRemoveAllTopics = () => {
        if (!config) return;
        if (window.confirm("Are you sure you want to remove all valid topics?")) {
            setConfig({ ...config, valid_topics: [] });
        }
    };

    const handleRemoveAllInvalidTopics = () => {
        if (!config) return;
        if (window.confirm("Are you sure you want to remove all invalid topics?")) {
            setConfig({ ...config, invalid_topics: [] });
        }
    };

    const handleSaveConfig = async () => {
        if (!config) return;
        setSavingConfig(true);
        setMessage('');
        try {
            const res = await axios.post(Endpoints.GUARDRAILS_CONFIG, config, axiosConfig);
            if (res.data) {
                setConfig(res.data);
                setMessage("Success: Guardrails configuration updated!");
            }
        } catch (err: any) {
            setMessage('Error: Failed to save config - ' + (err.response?.data?.detail || err.response?.data?.error || err.message));
        } finally {
            setSavingConfig(false);
        }
    };

    return (
        <div className="backoffice-container">
            <header className="backoffice-header">
                <h1>Guardrails Management</h1>
                <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                    <button onClick={() => navigate('/backoffice')} className="btn btn-primary">Document Backoffice</button>
                    <button onClick={() => navigate('/analysis-dashboard')} className="btn btn-primary">Analysis Dashboard</button>
                    <button onClick={() => navigate('/session-explorer')} className="btn btn-primary">Session Explorer</button>
                    <button onClick={() => navigate('/chat')} className="btn btn-secondary">Back to Chat</button>
                </div>
            </header>

            {message && (
                <div className={`alert ${message.toLowerCase().includes('error') ? 'alert-error' : 'alert-success'}`}>
                    {message}
                </div>
            )}

            <section className="section-card">
                <h2>AI Security & Safety Rules</h2>
                <p style={{ marginBottom: '1.5rem', fontSize: '0.9rem', color: '#555' }}>
                    Configure the active validators and allowed topics for the routing agent. 
                    Changes take effect immediately across all active sessions.
                </p>

                {config ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>

                        <section className="section-card" style={{ marginBottom: 0, border: '1px solid #eef2f7', background: '#fcfdff' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                <h3 style={{ margin: 0 }}>Validator Enforcement</h3>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleSelectAllValidators}
                                    >
                                        Enable All
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                        onClick={handleDeselectAllValidators}
                                    >
                                        Disable All
                                    </button>
                                </div>
                            </div>
                            <p style={{ marginBottom: '1.5rem', fontSize: '0.85rem', color: '#666' }}>Enable or disable specific validation rules for the AI agent.</p>

                            <div style={{
                                display: 'grid',
                                gridTemplateColumns: 'repeat(3, 1fr)',
                                gap: '1.25rem'
                            }}>
                                {Object.entries(config)
                                    .filter(([key]) => key !== 'valid_topics' && key !== 'invalid_topics')
                                    .map(([key, value]) => (
                                        <div key={key} className="form-group" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', margin: 0, position: 'relative' }}>
                                            <label className="switch">
                                                <input
                                                    type="checkbox"
                                                    checked={value as boolean}
                                                    onChange={() => handleConfigToggle(key as keyof GuardrailsConfig)}
                                                />
                                                <span className="slider round" />
                                            </label>
                                            <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', cursor: 'pointer', minWidth: 0 }} onClick={() => setActiveTooltip(activeTooltip === key ? null : key)}>
                                                <span style={{
                                                    fontSize: '0.8rem',
                                                    textTransform: 'capitalize',
                                                    color: '#333',
                                                    fontWeight: 500,
                                                    whiteSpace: 'nowrap',
                                                    overflow: 'hidden',
                                                    textOverflow: 'ellipsis'
                                                }}>
                                                    {key.split('_').join(' ')}
                                                </span>
                                                <span
                                                    style={{
                                                        background: '#3498db', border: 'none', borderRadius: '50%',
                                                        width: '14px', height: '14px', fontSize: '10px', flexShrink: 0,
                                                        display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white',
                                                        boxShadow: '0 1px 3px rgba(0,0,0,0.1)'
                                                    }}
                                                >
                                                    ?
                                                </span>
                                            </div>
                                            {activeTooltip === key && (
                                                <div
                                                    className="tooltip-popup"
                                                    onClick={() => setActiveTooltip(null)}
                                                >
                                                    <div style={{ fontWeight: 'bold', marginBottom: '4px', textTransform: 'capitalize', color: '#3498db' }}>{key.split('_').join(' ')}</div>
                                                    {validatorDescriptions[key] || "No description available."}
                                                    <div style={{ marginTop: '6px', fontSize: '0.65rem', color: '#bdc3c7', textAlign: 'right', fontStyle: 'italic' }}>Click to close</div>
                                                </div>
                                            )}
                                        </div>
                                    ))}
                            </div>
                        </section>

                        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
                            <section className="section-card" style={{ margin: 0, border: '1px solid #eef2f7', background: '#fcfdff' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                    <h3 style={{ margin: 0 }}>Valid Topics</h3>
                                    {config.valid_topics.length > 0 && (
                                        <button
                                            type="button"
                                            className="btn btn-danger"
                                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                            onClick={handleRemoveAllTopics}
                                        >
                                            Clear All
                                        </button>
                                    )}
                                </div>
                                <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '1rem' }}>These topics define the allowed scope for user inquiries.</p>

                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem', minHeight: '40px' }}>
                                    {config.valid_topics.map(topic => (
                                        <span key={topic} className="category-badge" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.3rem 0.6rem', fontSize: '0.8rem', background: '#e1f5fe', color: '#01579b' }}>
                                            {topic}
                                            <span onClick={() => handleRemoveTopic(topic)} style={{ cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}>&times;</span>
                                        </span>
                                    ))}
                                    {config.valid_topics.length === 0 && <p style={{ fontStyle: 'italic', color: '#999', fontSize: '0.8rem' }}>No topics defined.</p>}
                                </div>

                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Add valid topic..."
                                        value={newTopic}
                                        onChange={(e) => setNewTopic(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && handleAddTopic()}
                                        style={{ fontSize: '0.85rem' }}
                                    />
                                    <button type="button" className="btn btn-primary" onClick={handleAddTopic} style={{ padding: '0.3rem 0.8rem' }}>Add</button>
                                </div>
                            </section>

                            <section className="section-card" style={{ margin: 0, border: '1px solid #f9ebeb', background: '#fffafa' }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                                    <h3 style={{ margin: 0 }}>Forbidden Topics (Escalation)</h3>
                                    {config.invalid_topics.length > 0 && (
                                        <button
                                            type="button"
                                            className="btn btn-danger"
                                            style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem' }}
                                            onClick={handleRemoveAllInvalidTopics}
                                        >
                                            Clear All
                                        </button>
                                    )}
                                </div>
                                <p style={{ fontSize: '0.85rem', color: '#666', marginBottom: '1rem' }}>Topics that trigger immediate human escalation.</p>

                                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem', minHeight: '40px' }}>
                                    {config.invalid_topics.map(topic => (
                                        <span key={topic} className="category-badge" style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.3rem 0.6rem', fontSize: '0.8rem', background: '#ffebee', color: '#b71c1c' }}>
                                            {topic}
                                            <span onClick={() => handleRemoveInvalidTopic(topic)} style={{ cursor: 'pointer', fontWeight: 'bold', fontSize: '1rem' }}>&times;</span>
                                        </span>
                                    ))}
                                    {config.invalid_topics.length === 0 && <p style={{ fontStyle: 'italic', color: '#999', fontSize: '0.8rem' }}>No forbidden topics defined.</p>}
                                </div>

                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        type="text"
                                        className="form-control"
                                        placeholder="Add forbidden topic..."
                                        value={newInvalidTopic}
                                        onChange={(e) => setNewInvalidTopic(e.target.value)}
                                        onKeyPress={(e) => e.key === 'Enter' && handleAddInvalidTopic()}
                                        style={{ fontSize: '0.85rem' }}
                                    />
                                    <button type="button" className="btn btn-danger" onClick={handleAddInvalidTopic} style={{ padding: '0.3rem 0.8rem' }}>Add</button>
                                </div>
                            </section>
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'center', marginTop: '1rem', borderTop: '1px solid #eee', paddingTop: '2rem' }}>
                            <button
                                className="btn btn-success"
                                style={{ padding: '1rem 3rem', fontSize: '1.1rem', borderRadius: '12px', boxShadow: '0 4px 12px rgba(40, 167, 69, 0.2)' }}
                                onClick={handleSaveConfig}
                                disabled={savingConfig}
                            >
                                {savingConfig ? 'Applying Security Rules...' : 'Save & Apply Guardrails Policy'}
                            </button>
                        </div>
                    </div>
                ) : (
                    <p style={{ padding: '2rem', textAlign: 'center', color: '#666' }}>Loading Guardrails configuration...</p>
                )}
            </section>
        </div>
    );
}
