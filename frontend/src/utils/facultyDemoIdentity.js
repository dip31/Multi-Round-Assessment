export const FACULTY_DEMO_STUDENT_NAMES = [
    'Aarav Sharma',
    'Ananya Patel',
    'Rohan Deshmukh',
    'Priya Kulkarni',
    'Vivaan Mehta',
    'Isha Joshi',
    'Arjun Shah',
    'Sneha Pawar',
    'Aditya Verma',
    'Kavya Nair',
    'Rahul Chavan',
    'Neha Gupta',
    'Siddharth Rao',
    'Aditi More',
    'Karan Malhotra',
    'Meera Iyer',
    'Yash Thakur',
    'Pooja Singh',
    'Omkar Patil',
    'Tanvi Desai',
];

const UNRESOLVED_NAME = 'Student identity unavailable';

/**
 * Supplies a clearly marked name for table-only development evaluation.
 * The input record remains unchanged and the assignment map belongs to the
 * current page instance, so a row's demo name stays stable while it is open.
 */
export function facultyStudentDisplayIdentity(record, {
    isDevelopment,
    assignments,
    names = FACULTY_DEMO_STUDENT_NAMES,
}) {
    const realName = record?.student?.name;
    if (realName && realName !== UNRESOLVED_NAME) {
        return { name: realName, isDemo: false };
    }

    if (!isDevelopment || !assignments || names.length === 0) {
        return { name: realName || UNRESOLVED_NAME, isDemo: false };
    }

    const rowKey = record?.session_id !== undefined && record?.session_id !== null
        ? `${record.session_id}:${record?.round_id ?? 'round'}`
        : `student:${record?.student?.user_id ?? 'unknown'}`;
    if (!assignments.has(rowKey)) {
        assignments.set(rowKey, names[assignments.size % names.length]);
    }
    return { name: assignments.get(rowKey), isDemo: true };
}
