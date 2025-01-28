# NGINX Documentation Inventory Scraper

This script automates the collection of all documentation URLs under each NGINX product’s base URL and exports them to an Excel file.

## 📌 Features

✅ **Scrapes all URLs** under a given documentation set  
✅ **Filters out non-webpage files** (images, YAML, PDFs, etc.)  
✅ **Handles 404 errors gracefully** (skips missing pages)  
✅ **Saves results in an Excel file**, with each doc set as its own tab  
✅ **Displays real-time progress** while scraping  

---

## 📂 Repository Structure

``` text
content-strategy/scripts/page-scraper/
│── README.md               # Instructions & usage guide
│── doc_inventory_scraper.py # Python script
│── doc-set-base-links.csv   # CSV file containing doc set names & base URLs
```

---

## 🚀 How to Use

### **1. Install Python 3**

Check if Python is installed:

```sh
python3 --version
```

If not installed, download it from [python.org](https://www.python.org/downloads/).

### **2. Install Dependencies**

Install the required Python libraries:

```sh
pip install requests beautifulsoup4 pandas openpyxl
```

### **3. Clone the Repo**

```sh
git clone https://github.com/travisamartin/content-strategy.git
cd content-strategy/scripts/page-scraper
```

### **4. Run the Script**

```sh
python3 doc_inventory_scraper.py
```

### **5. Monitor the Script Execution**

The script will display progress in real-time:

- 🚀 Scraping doc set: **NGINX Plus** (https://docs.nginx.com/nginx/)
- 🔍 Visiting: https://docs.nginx.com/nginx/
- ✅ Completed scraping NGINX Plus. Found 42 pages.
- 📄 Saved results to: nginx_doc_inventory.xlsx

### **6. Open the Generated Excel File**

- The output file, `nginx_doc_inventory.xlsx`, will be saved in the same directory.
- Each documentation set will have its own **tab** in the Excel file.

---

## 📄 CSV File Format (`doc-set-base-links.csv`)

The CSV file is used to specify which NGINX documentation sets to inventory.  
You can **edit this file** to add or remove doc sets before running the script.

### **Columns:**
- **`Title`** → The name of the documentation set
- **`URL`** → The base URL of the documentation set

### **Example CSV Data:**
| Title                        | URL                                             |
|------------------------------|-------------------------------------------------|
| NGINX Agent                  | https://docs.nginx.com/nginx-agent/            |
| NGINX App Protect            | https://docs.nginx.com/nginx-app-protect/      |
| NGINX App Protect DoS        | https://docs.nginx.com/nginx-app-protect-dos/  |
| NGINX Gateway Fabric         | https://docs.nginx.com/nginx-gateway-fabric/   |
| NGINX Ingress Controller     | https://docs.nginx.com/nginx-ingress-controller/ |
| NGINX Instance Manager       | https://docs.nginx.com/nginx-instance-manager/ |
| NGINX Kubernetes Gateway     | https://docs.nginx.com/nginx-kubernetes-gateway/ |
| NGINX Management Suite       | https://docs.nginx.com/nginx-management-suite/ |
| NGINX One                    | https://docs.nginx.com/nginx-one/              |
| NGINX Plus                   | https://docs.nginx.com/nginx/                  |

### **Customizing the Inventory**
- To **exclude** a doc set, **remove** its row from `doc-set-base-links.csv`.
- To **include** a new doc set, **add** a new row with the doc set name and base URL.
- Ensure the CSV **does not contain extra spaces or missing headers** before running the script.

---

## 🛠 Troubleshooting

### **Issue: The script doesn’t run (command not found)**

- Ensure Python 3 is installed.
- Try using `python` instead of `python3`:

  ```sh
  python doc_inventory_scraper.py
  ```

### **Issue: Some URLs return 404 errors**

- These pages don’t exist and are skipped automatically.
- If an important page is missing, verify it manually in a browser.

### **Issue: The Excel file isn’t generated**

- Check if the script completed successfully.
- Ensure there are no permission issues in the directory.

---

## 📌 Summary

| Step | Action |
|------|--------|
| 1 | Install Python 3 & dependencies |
| 2 | Clone the repository |
| 3 | Run the script |
| 4 | Monitor the URLs being scraped |
| 5 | Find `nginx_doc_inventory.xlsx` in the script directory |
| 6 | Open the Excel file and review the data |

---

## 📜 License

This script is available under the [MIT License](https://opensource.org/licenses/MIT). Feel free to modify and improve it!

---

## 🤝 Contributions

Contributions, bug reports, and feature requests are welcome! Fork the repo and submit a PR.

📌 **GitHub Repo:** [travisamartin/content-strategy](https://github.com/travisamartin/content-strategy/tree/main/scripts/page-scraper)