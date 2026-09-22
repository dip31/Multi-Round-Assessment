/**
 * StudentLayout — wraps student-facing pages with the persistent left sidebar.
 *
 * Usage:
 *   <StudentLayout>
 *     <YourPage />
 *   </StudentLayout>
 *
 * The sidebar handles its own sticky positioning.
 * The main area scrolls independently.
 */
import StudentSidebar from './StudentSidebar';

export default function StudentLayout({ children }) {
    return (
        <div className="flex min-h-screen bg-slate-50">
            <StudentSidebar />
            <main className="flex-1 min-w-0 overflow-x-hidden">
                {children}
            </main>
        </div>
    );
}
