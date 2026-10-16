"use client";

import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { PostCard } from "@/components/cards";
import { ProfileBody, ProfileHeader } from "@/components/profile-header";
import { Empty, Icon, Skeletons, TopBar } from "@/components/ui";
import { api, ApiError, del, post } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Page, Post, Profile } from "@/lib/types";

export default function ProfilePage() {
  const { id } = useParams<{ id: string }>();
  const { me } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [posts, setPosts] = useState<Post[]>([]);
  const [missing, setMissing] = useState(false);

  const load = useCallback(async () => {
    try {
      const p = await api<Profile>(`/profiles/${id}`);
      setProfile(p);
      setPosts((await api<Page<Post>>(`/posts?author=${p.user_id}`)).results);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) setMissing(true);
    }
  }, [id]);
  useEffect(() => { load(); }, [load, me]);

  if (missing) return (<><TopBar back title="Profile" /><Empty icon="🔒" title="This profile isn't available" /></>);
  if (!profile) return (<><TopBar back title="Profile" /><div className="page"><Skeletons n={2} /></div></>);
  const isMe = me?.id === profile.user_id;

  const follow = async () => {
    if (!me) return router.push("/login");
    if (profile.viewer_is_following) await del(`/users/${profile.user_id}/follow`);
    else await post(`/users/${profile.user_id}/follow`);
    load();
  };
  const message = async () => {
    if (!me) return router.push("/login");
    const c = await post<{ id: string }>("/conversations", { user_id: profile.user_id });
    router.push(`/inbox/${c.id}`);
  };

  return (
    <>
      <TopBar back title={profile.display_name} />
      <div className="page">
        <ProfileHeader profile={profile} actions={!isMe && (
          <>
            <button className={`btn grow ${profile.viewer_is_following ? "ghost" : "primary"}`} onClick={follow}>
              {profile.viewer_is_following ? "Following" : "Follow"}
            </button>
            <button className="btn ghost grow" onClick={message}><Icon name="inbox" size={18} />Message</button>
          </>
        )} />
        <ProfileBody profile={profile} />
        <div className="section-title">Posts</div>
        {posts.length === 0 ? <p className="muted small">No posts yet.</p> : posts.map((p) => <PostCard key={p.id} post={p} />)}
      </div>
    </>
  );
}
