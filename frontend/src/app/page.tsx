import styles from "./page.module.css";
import Chat from "@/components/chat/chat";

export default function Home() {
  return (
    <div className={styles.page}>
      <main className={styles.main}>
        <div className={styles.intro}>
          <h1>Assessment App</h1>
          <p>
            This is a simple app that allows you to ask questions to a document.
          </p>
          
        </div>
        <Chat />
      </main>
    </div>
  );
}
