"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { api } from "@/lib/api";
const navItems = [
  { href: "/", label: "Dashboard", icon: "\u{1F4CA}" },
  { href: "/upload", label: "Upload", icon: "\u{1F4E4}" },
  { href: "/documents", label: "Documents", icon: "\u{1F4C1}" },
  { href: "/inventory", label: "Inventory", icon: "\u{1F4CB}" },
  { href: "/extraction", label: "Extraction", icon: "\u{2699}\u{FE0F}" },
  { href: "/accuracy", label: "Accuracy", icon: "\u{1F3AF}" },
  { href: "/insights", label: "Insights", icon: "\u{1F4A1}" },
];

function generateId(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "")
    .substring(0, 30);
}

export default function Sidebar() {
  const pathname = usePathname();
  const [projects, setProjects] = useState<{ id: string; name: string }[]>([]);
  const [activeProject, setActiveProject] = useState("nss");
  const [showNewProject, setShowNewProject] = useState(false);
  const [newName, setNewName] = useState("");
  const [mounted, setMounted] = useState(false);

  // Only read localStorage after mount — validate project exists
  useEffect(() => {
    setMounted(true);
    api.getProjects().then((projectList) => {
      setProjects(projectList);
      const stored = localStorage.getItem("dd_active_project");
      if (stored && projectList.some((p) => p.id === stored)) {
        setActiveProject(stored);
      } else {
        // Reset to default if stored project doesn't exist
        localStorage.setItem("dd_active_project", "nss");
        setActiveProject("nss");
      }
    }).catch(() => {
      const stored = localStorage.getItem("dd_active_project");
      if (stored) setActiveProject(stored);
    });
  }, []);

  async function handleCreateProject() {
    const name = newName.trim();
    if (!name) return;
    const id = generateId(name);
    if (!id) return;
    try {
      const proj = await api.createProject(id, name);
      setProjects((prev) => [...prev, proj]);
      setActiveProject(proj.id);
      setShowNewProject(false);
      setNewName("");
      localStorage.setItem("dd_active_project", proj.id);
      window.location.reload();
    } catch (e) {
      alert(`Failed to create project: ${e}`);
    }
  }

  function switchProject(pid: string) {
    setActiveProject(pid);
    localStorage.setItem("dd_active_project", pid);
    window.location.reload();
  }

  // Render a static placeholder until client-side mount completes
  // This prevents the hydration mismatch between server and client
  // IMPORTANT: No interactive components (NotificationBell etc) in this block
  if (!mounted) {
    return (
      <aside className="w-64 bg-zinc-900 border-r border-zinc-800 flex flex-col shrink-0">
        <div className="p-6 border-b border-zinc-800">
          <h1 className="text-lg font-bold text-white">Digital Direction</h1>
          <p className="text-xs text-zinc-400 mt-1">Inventory Platform</p>
        </div>
        <div className="mx-3 mt-3">
          <p className="text-xs text-zinc-500 px-1 mb-1">Project</p>
          <div className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-400">
            Loading...
          </div>
        </div>
        <nav className="flex-1 p-3 mt-2">
          {navItems.map((item) => (
            <div key={item.href}
              className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm text-zinc-300 mb-0.5">
              <span className="text-base">{item.icon}</span>
              {item.label}
            </div>
          ))}
        </nav>
        <div className="p-4 border-t border-zinc-800">
          <p className="text-xs text-zinc-500">POC v1.0 — Techjays</p>
        </div>
      </aside>
    );
  }

  return (
    <aside className="w-64 bg-zinc-900 border-r border-zinc-800 flex flex-col shrink-0">
      <div className="p-6 border-b border-zinc-800">
        <h1 className="text-lg font-bold text-white">Digital Direction</h1>
        <p className="text-xs text-zinc-400 mt-1">Inventory Platform</p>
      </div>

      {/* Project Switcher */}
      <div className="mx-3 mt-3">
        <p className="text-xs text-zinc-500 px-1 mb-1">Project</p>
        <select
          value={activeProject}
          onChange={(e) => {
            if (e.target.value === "__new__") {
              setShowNewProject(true);
            } else {
              switchProject(e.target.value);
            }
          }}
          className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-white"
        >
          {projects.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
          <option value="__new__">+ New Project...</option>
        </select>

        {showNewProject && (
          <div className="mt-2 p-3 bg-zinc-800 rounded-lg border border-zinc-700 space-y-2">
            <input
              placeholder="Project Name (e.g. City of Dublin)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="w-full bg-zinc-900 border border-zinc-600 rounded px-2 py-1.5 text-xs"
              autoFocus
              onKeyDown={(e) => { if (e.key === "Enter") handleCreateProject(); }}
            />
            {newName.trim() && (
              <p className="text-xs text-zinc-500">
                ID: <span className="text-zinc-400 font-mono">{generateId(newName)}</span>
              </p>
            )}
            <div className="flex gap-2">
              <button onClick={handleCreateProject}
                disabled={!newName.trim()}
                className="flex-1 bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 disabled:text-zinc-500 text-white text-xs py-1.5 rounded">
                Create
              </button>
              <button onClick={() => { setShowNewProject(false); setNewName(""); }}
                className="flex-1 bg-zinc-700 hover:bg-zinc-600 text-xs py-1.5 rounded">
                Cancel
              </button>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 mt-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== "/" && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors mb-0.5 ${
                isActive
                  ? "bg-blue-600/20 text-blue-300 border border-blue-500/20"
                  : "text-zinc-300 hover:bg-zinc-800 hover:text-white"
              }`}>
              <span className="text-base">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>
      <div className="p-4 border-t border-zinc-800">
        <p className="text-xs text-zinc-500">POC v1.0 — Techjays</p>
      </div>
    </aside>
  );
}
