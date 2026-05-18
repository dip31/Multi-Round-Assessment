import { CheckCircle2, PlayCircle, UserPlus, Clock } from "lucide-react";

export function ActivityFeed() {
  const activities = [
    {
      id: 1,
      title: "Submitted Two Sum",
      time: "2 mins ago",
      icon: CheckCircle2,
      color: "text-teal-500 bg-teal-500/10",
      type: "success"
    },
    {
      id: 2,
      title: "Started Round 2 (Coding)",
      time: "1 hour ago",
      icon: PlayCircle,
      color: "text-accent bg-accent/10",
      type: "action"
    },
    {
      id: 3,
      title: "Registered for Drive",
      time: "2 hours ago",
      icon: UserPlus,
      color: "text-blue-500 bg-blue-500/10",
      type: "info"
    }
  ];

  return (
    <div className="rounded-xl border border-gray-100 bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-center gap-2">
        <Clock className="h-5 w-5 text-muted-foreground" />
        <h3 className="font-heading text-lg font-bold text-heading">Recent Activity</h3>
      </div>
      
      <div className="relative space-y-6 before:absolute before:inset-y-0 before:left-[19px] before:-z-10 before:w-px before:bg-gray-100">
        {activities.map((activity) => {
          const Icon = activity.icon;
          return (
            <div key={activity.id} className="relative flex items-start gap-4 z-10">
              <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ring-4 ring-white ${activity.color}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div className="flex flex-col pt-1">
                <span className="text-sm font-semibold text-heading">{activity.title}</span>
                <span className="text-xs font-medium text-muted-foreground">{activity.time}</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
