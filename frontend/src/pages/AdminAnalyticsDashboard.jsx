import React, { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import AdminLayout from '../components/AdminLayout';
import api from '../services/api';
import PageSkeleton from '../components/shared/PageSkeleton';

export default function AdminAnalyticsDashboard() {
    const [stats, setStats] = useState(null);
    const [skillGaps, setSkillGaps] = useState([]);
    const [totalTurnsAnalyzed, setTotalTurnsAnalyzed] = useState(0);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        const fetchDashboardData = async () => {
            try {
                const [statsRes, skillsRes] = await Promise.all([
                    api.get('/report/admin/cohort-stats'),
                    api.get('/report/admin/skill-gaps'),
                ]);
                
                setStats(statsRes.data);
                setTotalTurnsAnalyzed(skillsRes.data.total_turns_analyzed || 0);
                
                // Format skill gaps for Recharts
                // Sort: real topics first (by struggle rate desc), General last
                const topics = skillsRes.data.topics || [];
                const generalTopic = topics.find(t => t.topic === 'General');
                const otherTopics = topics.filter(t => t.topic !== 'General');
                
                // Only include General if it has high struggle rate (>30%)
                const sortedTopics = generalTopic && generalTopic.struggle_rate > 0.3
                    ? [...otherTopics, generalTopic]
                    : otherTopics;
                
                const formattedGaps = sortedTopics.map(topic => ({
                    name: topic.topic === 'General' ? 'General / Unclassified' : topic.topic,
                    rate: parseFloat((topic.struggle_rate * 100).toFixed(1)),
                    count: topic.candidate_count,
                    isGeneral: topic.topic === 'General'
                }));
                setSkillGaps(formattedGaps);
            } catch (err) {
                console.error("Failed to load admin dashboard data", err);
            } finally {
                setLoading(false);
            }
        };

        fetchDashboardData();
    }, []);

    const getBarColor = (entry) => {
        if (entry.isGeneral) return '#94a3b8'; // slate-400 for General
        if (entry.rate > 60) return '#ef4444'; // red
        if (entry.rate > 30) return '#f59e0b'; // amber
        return '#22c55e'; // green
    };

    // Check if only "General" topic exists
    const onlyGeneralTopic = skillGaps.length === 1 && skillGaps[0]?.isGeneral;
    const noSkillData = skillGaps.length === 0;

    if (loading) {
        return (
            <AdminLayout>
                <PageSkeleton variant="light" embedded cardCount={4} />
            </AdminLayout>
        );
    }

    if (!stats || stats.total_candidates === 0) {
        return (
            <AdminLayout>
                <div className="text-center mt-20 p-8 bg-white rounded-xl border border-slate-200 shadow-sm max-w-lg mx-auto">
                    <h3 className="text-xl font-bold text-slate-800 mb-2">No Candidates Found</h3>
                    <p className="text-slate-500">Wait for candidates to complete assessments to generate analytics.</p>
                </div>
            </AdminLayout>
        );
    }

    return (
        <AdminLayout>
            <div className="max-w-6xl mx-auto space-y-6">
                <div>
                    <h1 className="text-2xl font-bold text-slate-900">Analytics Overview</h1>
                    <p className="text-slate-500 text-sm">Real-time aggregate performance data</p>
                </div>

                {/* Cohort Stats Strip */}
                <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wide mb-1">Total Candidates</p>
                        <p className="text-3xl font-bold text-slate-900">{stats.total_candidates}</p>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wide mb-1">Avg Score</p>
                        <p className="text-3xl font-bold text-blue-600">{(stats.avg_overall_score * 100).toFixed(1)}%</p>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wide mb-1">Avg Completion</p>
                        <p className="text-3xl font-bold text-slate-900">{(stats.completion_rates?.all_three * 100 || 0).toFixed(0)}%</p>
                    </div>
                    <div className="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
                        <p className="text-slate-500 text-xs font-semibold uppercase tracking-wide mb-1">Avg Response Time</p>
                        <p className="text-3xl font-bold text-slate-900">{stats.avg_response_time?.toFixed(1) || 0}s</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                    {/* Skill Gaps Chart */}
                    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm">
                        <div className="flex items-center justify-between mb-4">
                            <h2 className="text-lg font-bold text-slate-800">Skill Gaps (Struggle Rate %)</h2>
                            {totalTurnsAnalyzed > 0 && (
                                <span className="text-xs text-slate-400">{totalTurnsAnalyzed} questions analyzed</span>
                            )}
                        </div>
                        <div className="h-72">
                            {onlyGeneralTopic || noSkillData ? (
                                <div className="h-full flex flex-col items-center justify-center">
                                    <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 max-w-sm text-center">
                                        <div className="text-amber-600 text-2xl mb-2">📊</div>
                                        <p className="text-amber-700 text-sm font-medium">
                                            Topic classification is warming up.
                                        </p>
                                        <p className="text-amber-600 text-xs mt-1">
                                            More interview data needed for skill gap analysis.
                                        </p>
                                    </div>
                                </div>
                            ) : skillGaps.length > 0 ? (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={skillGaps} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                                        <XAxis type="number" domain={[0, 100]} />
                                        <YAxis dataKey="name" type="category" width={120} tick={{ fontSize: 12, fill: '#64748b' }} />
                                        <Tooltip 
                                            cursor={{ fill: '#f8fafc' }} 
                                            formatter={(value, name, props) => [`${value}% struggle rate`, props.payload.count + ' candidates']} 
                                        />
                                        <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
                                            {skillGaps.map((entry, index) => (
                                                <Cell key={`cell-${index}`} fill={getBarColor(entry)} />
                                            ))}
                                        </Bar>
                                    </BarChart>
                                </ResponsiveContainer>
                            ) : (
                                <div className="h-full flex items-center justify-center text-slate-400 text-sm">
                                    Not enough data points yet
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Breakdown by Module */}
                    <div className="bg-white p-6 rounded-xl border border-slate-200 shadow-sm flex flex-col justify-between">
                        <div>
                            <h2 className="text-lg font-bold text-slate-800 mb-4">Module Averages</h2>
                            <div className="space-y-6">
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span className="font-medium text-slate-600">Aptitude</span>
                                        <span className="font-bold">{(stats.avg_aptitude_score * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                                        <div className="bg-blue-500 h-full rounded-full" style={{ width: `${stats.avg_aptitude_score * 100}%` }}></div>
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span className="font-medium text-slate-600">Coding</span>
                                        <span className="font-bold">{(stats.avg_coding_score * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                                        <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${stats.avg_coding_score * 100}%` }}></div>
                                    </div>
                                </div>
                                <div>
                                    <div className="flex justify-between text-sm mb-1">
                                        <span className="font-medium text-slate-600">Interview</span>
                                        <span className="font-bold">{(stats.avg_interview_score * 100).toFixed(1)}%</span>
                                    </div>
                                    <div className="w-full bg-slate-100 h-2.5 rounded-full overflow-hidden">
                                        <div className="bg-purple-500 h-full rounded-full" style={{ width: `${stats.avg_interview_score * 100}%` }}></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </AdminLayout>
    );
}
