In backend c'è un pacchetto python espone un servizio AI che dve essere integrato con il contentuo della cartella frontend. 

Come prima operazione dovrai leggere tutto il contenuto della cartella backend per avere chiaro le funzionalità già disponibili. 
Poi dovrai leggere il contenuto della cartella frontend per poter integrare il backend con il frontend e rimuovere i mock.

- La chat dovrà essere integrata con l'ednpoint in streaming della chat.
- Le infromazioni presenti nella sidebar a sinsitra (obiettivo, stipendio mensile, spese fisse, disponibile, risparmio mensile) dovranno essere prese direttamente nella tabella user. Se nella tabella user non ci sono aggiungili nel backend.
    - Il disponibile deve essere calcolato come differenza tra Stipendio (che è un valore inserito dall'utente) - Spese fisse (calcolate dall'AI rispetto alle spese dei mesi prima)
    - Il disponibile mensile è il disponibile diviso per 5.
    - Il risparmio mensile è il totale delle entrate del mese corrente meno il totale delle spese del mese corrente.

La parte di sotto mostra il totale di spese per settimana. L'utente può cambiare la settimana.   

Per adesso ignora la sidebar a destra di insights AI e ignora l'estratto conto in basso a sinsitra della sidebar di destra