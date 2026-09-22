/**
 * StudentModeLayout — wraps student pages with the mode-aware sidebar and minimal header.
 * 
 * The sidebar changes based on the current mode (Practice/Portfolio/Mock Drive).
 * The header only contains branding and user profile, no primary navigation.
 */
import StudentModeSidebar from './StudentModeSidebar';

export default function StudentModeLayout({ children }) {
    return (
        <div className="flex min-h-screen bg-slate-50">
            <StudentModeSidebar />
            <main className="flex-1 min-w-0 overflow-x-hidden">
                {children}
            </main>
        </div>
    );
}
