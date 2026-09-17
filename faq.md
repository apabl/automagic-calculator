##### What is this app for?
You add cards and enter vendor reference prices in the top section, then manage your quantities and check off items in the final prices section below. The app automatically computes everything in pesos, allowing you to easily compare all vendor options side by side.

##### How do I add or remove a card?
Use the **"Add card"** dropdown above the main grid to search and select a card. To remove cards, click the thrash icon at the right of the column.

##### Why are there some cards I don't even know?
Three random cards are loaded as placeholders to show some of the app's functionality. Feel free to remove them and add your own!

##### How is the Dólar Blue rate updated?
The app automatically fetches the current Dólar Blue "venta" rate from the internet upon loading. You can also manually adjust the Agora Dólar Reference from the sidebar.

##### How are the "Cheapest Price" and "Cheapest Edition" columns updated?
They're fetched from Card Kingdom's pricelist. If a card has multiple versions, the app automatically selects the cheapest non-foil option. These values are locked to the card afterward — removing and re-adding a card will refresh them against the current pricelist.

##### What do the different columns represent?
**Card Kingdom** and **CoolStuffInc** use standard middleman service calculation rules. **Multi Margin** allows you to simulate a market by adding a percentage to the dollar price along with a fixed amount per card (in pesos). **Agora** uses the base price with a customizable dollar reference, as each vendor chooses its own exchange rate.

##### What are the checkmarks (✓) used for in the Final Prices section?
Checking the boxes next to items allows you to dynamically sum up specific subsets of cards and calculate subtotals for what you plan to order from each vendor.

##### Is my data or price information stored in the cloud?
No. The app does not store any data on a server or in the cloud. All computations are done on the fly in your active session. You can safely keep your progress locally by using the **Save to .csv** and file loader buttons in the sidebar.

##### Why does the save button download directly without asking where to save?
By default, most web browsers save files automatically to your computer's "Downloads" folder for speed and security. If you prefer a native window to prompt you for a custom location and file name every time, you can change this in your browser settings:  
* **Chrome / Edge / Brave:** Go to **Settings > Downloads** and turn on **"Ask where to save each file before downloading"**.
* **Firefox:** Go to **Settings > General > Files and Applications** and select **"Always ask you where to save files"**.

##### Which fields are automated and which are manual?
* **Automated:** Cheapest edition, Cheapest price (set when a card is added, or refreshed on file load), and the current Dólar Blue rate.
* **Manual:** Which cards are added/removed, quantities, vendor reference prices (CK, CS, MM, Ago), checkmarks, and the sidebar variables.