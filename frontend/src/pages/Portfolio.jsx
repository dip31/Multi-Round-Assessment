import React from 'react';
import Navbar from '../components/Navbar';
import PortfolioView from '../components/portfolio/PortfolioView';

export default function Portfolio() {
    return (
        <div className="min-h-screen bg-slate-50 font-['Inter'] antialiased">
            <Navbar position="sticky" />
            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <PortfolioView />
            </main>
        </div>
    );
}
