import React from 'react';
import StudentModeLayout from '../components/StudentModeLayout';
import PortfolioView from '../components/portfolio/PortfolioView';

export default function Portfolio() {
    return (
        <StudentModeLayout>
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
                <PortfolioView />
            </div>
        </StudentModeLayout>
    );
}
